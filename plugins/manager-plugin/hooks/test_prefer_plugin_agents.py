"""Tests for the plugin hooks (prefer-plugin-agents.sh, codemap-commit-check.sh,
codemap-rules-version.sh) and for the shell commands the manager skill's references give
(the briefs' plan-section read, the ignored-data guard in dispatch.md):
python3 -m unittest discover -s <this folder>"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "prefer-plugin-agents.sh")
COMMIT_HOOK = os.path.join(HERE, "codemap-commit-check.sh")
RULES_HOOK = os.path.join(HERE, "codemap-rules-version.sh")
CODEMAP = os.path.join(HERE, "..", "skills", "code-map", "scripts", "codemap.py")
SKILLS = os.path.join(HERE, "..", "skills")
MANAGER = os.path.join(SKILLS, "manager")
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")


def run(payload):
    data = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run(["sh", HOOK], input=data.encode(), capture_output=True)
    return p.returncode, p.stderr.decode()


def spawn(**tool_input):
    return {"tool_name": "Agent", "tool_input": tool_input}


class HookTest(unittest.TestCase):
    def test_general_purpose_is_blocked_with_guidance(self):
        code, err = run(spawn(subagent_type="general-purpose", prompt="fix the bug"))
        self.assertEqual(code, 2)
        for agent in ("worker", "researcher", "reviewer"):
            self.assertIn("manager-plugin:" + agent, err)
        self.assertNotIn("implementer", err)

    def test_missing_type_defaults_to_general_purpose(self):
        self.assertEqual(run(spawn(prompt="x", description="d"))[0], 2)

    def test_other_agents_pass(self):
        for t in ("manager-plugin:worker", "manager-plugin:implementer", "Explore", "Plan"):
            self.assertEqual(run(spawn(subagent_type=t, prompt="x"))[0], 0, t)

    def test_escape_hatch(self):
        p = spawn(subagent_type="general-purpose", prompt="[general-purpose: needs Gmail] x")
        self.assertEqual(run(p)[0], 0)

    def test_quoted_text_in_prompt_is_not_the_field(self):
        p = spawn(subagent_type="Explore", prompt='say "subagent_type": "general-purpose"')
        self.assertEqual(run(p)[0], 0)

    def test_pretty_printed_input(self):
        data = json.dumps(spawn(subagent_type="general-purpose", prompt="x"), indent=2)
        self.assertEqual(run(data)[0], 2)

    def test_null_type_and_name_variants_are_blocked(self):
        self.assertEqual(run(spawn(subagent_type=None, prompt="x"))[0], 2)
        for t in ("General-Purpose", "general_purpose", "GeneralPurpose"):
            self.assertEqual(run(spawn(subagent_type=t, prompt="x"))[0], 2, t)

    def test_hook_entry_fails_open_on_windows_without_bash(self):
        with open(os.path.join(os.path.dirname(HOOK), "hooks.json")) as fh:
            entry = json.load(fh)["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(entry.get("onFailure"), "continue")

    def test_unexpected_input_fails_open(self):
        self.assertEqual(run("not json")[0], 0)
        self.assertEqual(run("")[0], 0)


class CodemapCommitCheckTest(unittest.TestCase):
    """codemap-commit-check.sh: blocks a `git commit` only in an opted-in repo with a stale map."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "repo")
        self.env = dict(ENV, HOME=self.tmp)
        self.write("src/app.py", "def run():\n    pass\n")
        self.write("vault/index.md", "- [[map]]\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.codemap("build")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="\n") as fh:
            fh.write(text)

    def git(self, *args):
        os.makedirs(self.root, exist_ok=True)
        subprocess.run(["git", "-C", self.root] + list(args), check=True, capture_output=True,
                       env=self.env)

    def codemap(self, *args):
        return subprocess.run(["python3", CODEMAP] + list(args) + ["--root", self.root],
                              capture_output=True, env=self.env).returncode

    def opt_in(self):
        self.write(".codemap.json", '{"vault": "vault", "map": "vault/map.md", '
                   '"commit_check": true}\n')
        self.codemap("build")

    def hook(self, command, cwd=None):
        data = json.dumps({"tool_name": "Bash", "cwd": cwd or self.root,
                           "tool_input": {"command": command}})
        p = subprocess.run(["sh", COMMIT_HOOK], input=data.encode(), capture_output=True,
                           env=self.env)
        return p.returncode, p.stderr.decode()

    def test_non_commit_commands_pass(self):
        self.opt_in()
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        for cmd in ("git status", "git log --grep commit", "ls", "git commit-tree x"):
            self.assertEqual(self.hook(cmd)[0], 0, cmd)

    def test_without_opt_in_it_passes(self):
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        self.assertEqual(self.codemap("check"), 1)
        self.assertEqual(self.hook("git commit -m x")[0], 0)

    def test_opted_in_stale_map_blocks_the_commit(self):
        self.opt_in()
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        code, err = self.hook("git add -A && git commit -m 'add new'")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("codemap.py\" build", err)
        self.assertIn("vault/map.md", err)
        for cmd in ('git -C "%s" commit -m x' % self.root, "cd %s && git commit -m x" % self.root,
                    "echo git commit"):
            self.assertEqual(self.hook(cmd, cwd=self.tmp)[0], 0, cmd)  # can't tell: fail open

    def test_the_stale_line_names_only_what_git_add_can_take(self):
        """A one-page map has no page folder: `git add vault/map.md vault/map/` would fail on
        the folder and stage nothing. The hook runs before the command starts, so a build or a
        `git add` chained in front of the commit is blocked like the bare commit."""
        self.opt_in()
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        code, err = self.hook("git commit -m x")
        self.assertEqual(code, 2)
        self.assertIn("then `git add -- vault/map.md`, each as a command of its own", err)
        self.assertNotIn("vault/map/", err)
        self.assertIn("one chained with the commit is not seen", err)
        chained = ('python3 "%s" build && git add vault/map.md && git commit -m x'
                   % CODEMAP.replace("\\", "/"))
        self.assertEqual(self.hook(chained), (code, err))
        self.assertEqual(self.codemap("build"), 0)  # the two commands the line names, in turn
        self.git("add", "--", "vault/map.md")
        self.assertEqual(self.hook("git commit -m x"), (0, ""))

    def test_a_rebuilt_map_left_unstaged_blocks_the_commit(self):
        """After `build` the working tree's map is current, but a commit takes the index: with
        the page not added, the stale map would be committed beside the new source file."""
        self.opt_in()
        self.git("add", "-A")
        self.git("commit", "-qm", "opt in")
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        self.assertEqual(self.hook("git commit -m x")[0], 2)
        self.assertEqual(self.codemap("build"), 0)
        self.assertEqual(self.codemap("check"), 0)
        before = snapshot(self.root)
        for command in ("git commit -m x", "git add -A && git commit -m x"):
            code, err = self.hook(command)
            self.assertEqual(code, 2, command)
            self.assertEqual(len(err.strip().splitlines()), 1)
            self.assertTrue(err.startswith("codemap: the code map is rebuilt but not staged (1 "
                                           "page the index does not hold as built)"), err)
            self.assertIn("run `git add -- vault/map.md` as a command of its own", err)
            self.assertNotIn("vault/map/", err)
            self.assertNotIn(" build", err)
        self.assertEqual(snapshot(self.root), before)  # the index included: nothing is written
        self.git("add", "--", "vault/map.md")
        self.assertEqual(self.hook("git commit -m x"), (0, ""))
        self.git("commit", "-qm", "new")
        self.assertEqual(self.hook("git commit --amend --no-edit"), (0, ""))

    def test_opted_in_current_map_passes(self):
        self.opt_in()
        self.assertEqual(self.hook("git commit -m x")[0], 0)

    def test_installed_git_hook_takes_over(self):
        self.opt_in()
        self.git("add", "-A")
        self.git("commit", "-qm", "opt in")
        self.assertEqual(self.codemap("install-hook"), 0)
        self.write("src/new.py", "def fresh():\n    pass\n")
        self.git("add", "-A")
        self.assertEqual(self.hook("git commit -m x")[0], 0)

    def test_errors_fail_open(self):
        self.opt_in()
        self.write("vault/map/hand.md", "hand-written\n")
        self.assertEqual(self.hook("git commit -m x")[0], 0)
        self.assertEqual(self.hook("git commit", cwd=os.path.join(self.tmp, "nowhere"))[0], 0)
        self.assertEqual(run_commit_hook("not json"), 0)

    def test_commit_hook_entry_fails_open(self):
        with open(os.path.join(HERE, "hooks.json")) as fh:
            entries = json.load(fh)["hooks"]["PreToolUse"]
        bash = [e for e in entries if e["matcher"] == "Bash"][0]["hooks"][0]
        self.assertEqual(bash.get("onFailure"), "continue")
        self.assertIn("codemap-commit-check.sh", bash["command"])


def run_commit_hook(data):
    return subprocess.run(["sh", COMMIT_HOOK], input=data.encode(), capture_output=True,
                          env=ENV).returncode


def snapshot(folder):
    """{relative path: bytes (None for a folder)} of everything under the folder."""
    found = {}
    for base, dirs, files in os.walk(folder):
        for name in dirs:
            found[os.path.relpath(os.path.join(base, name), folder)] = None
        for name in files:
            path = os.path.join(base, name)
            with open(path, "rb") as fh:
                found[os.path.relpath(path, folder)] = fh.read()
    return found


OLD_BEGIN = "<!-- manager-plugin:code-map:begin (managed by the code-map skill) -->"
RULES_END = "<!-- manager-plugin:code-map:end -->"
VIA_IMPORT = "<!-- manager-plugin:code-map: the code-map block comes via @AGENTS.md -->"


class RulesVersionHookTest(unittest.TestCase):
    """codemap-rules-version.sh (SessionStart): one stdout line when the rules block is older than
    the plugin's template; silent, exit 0 and nothing written everywhere else."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "my repo")
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "src", "pkg"))
        self.env = dict(ENV, HOME=self.tmp)
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def old_block(self, begin=OLD_BEGIN):
        return "# Rules\n\nKeep this.\n\n%s\n- an old line\n%s\n" % (begin, RULES_END)

    def rules_hint(self):
        p = subprocess.run(["python3", CODEMAP, "rules-hint", "--root", self.root],
                           capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr.decode())

    def hook(self, cwd=None, raw=None, source="startup"):
        data = raw if raw is not None else json.dumps(
            {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": cwd or self.root,
             "hook_event_name": "SessionStart", "source": source})
        p = subprocess.run(["sh", RULES_HOOK], input=data.encode(), capture_output=True,
                           env=self.env, cwd=self.tmp)  # input without a cwd: not a repository
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def assert_silent(self, **kw):
        self.assertEqual(self.hook(**kw), (0, "", ""), kw)

    def test_current_block_is_silent(self):
        self.rules_hint()  # creates both files with the current, versioned block
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertRegex(self.read(name), r"(?m)^<!-- manager-plugin:code-map:begin v\d+ \(")
        self.assert_silent()
        self.assert_silent(cwd=os.path.join(self.root, "src", "pkg"), source="resume")

    def test_old_unversioned_block_prints_one_line_with_the_command(self):
        self.write("AGENTS.md", self.old_block())
        for cwd in (self.root, os.path.join(self.root, "src", "pkg")):
            code, out, err = self.hook(cwd=cwd)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(len(out.splitlines()), 1, out)
            script = os.path.normpath(CODEMAP)
            self.assertEqual(out, "manager-plugin: the code-map rules block in AGENTS.md is older "
                             "than this plugin's template; `python3 \"%s\" rules-hint --root "
                             "\"%s\"` updates it; a manager run does this in its setup PR.\n"
                             % (script, self.root))
            told = out.replace(script, "").replace(self.root, "")  # information, not an order
            self.assertNotRegex(told, r"(?i)\bcommit|\brun `|\bmust\b|\bshould\b")
        command = re.search(r"`(.+)`", out).group(1)  # the printed command does the update
        p = subprocess.run(["sh", "-c", command], capture_output=True, env=self.env, cwd=self.tmp)
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        self.assertNotIn(OLD_BEGIN, self.read("AGENTS.md"))
        self.assertTrue(self.read("AGENTS.md").startswith("# Rules\n\nKeep this.\n\n<!-- "))
        self.assert_silent()

    def test_unversioned_block_is_current_only_with_the_template_text(self):
        self.rules_hint()
        for name in ("AGENTS.md", "CLAUDE.md"):  # as plugin 0.8.2 wrote it: no version
            text = self.read(name)
            unversioned = re.sub(r"(code-map:begin) v\d+ \(", r"\1 (", text)
            self.assertNotEqual(unversioned, text, name)
            self.write(name, unversioned)
        self.assert_silent()
        self.assert_silent(cwd=os.path.join(self.root, "src", "pkg"), source="resume")
        changed = self.read("AGENTS.md").replace("- Before searching", "- Before you search")
        self.assertNotEqual(changed, self.read("AGENTS.md"))
        self.write("AGENTS.md", changed)  # a real text change still counts as older
        out = self.hook()[1]
        self.assertEqual(len(out.splitlines()), 1, out)
        self.assertIn("rules block in AGENTS.md is older", out)
        self.assertNotIn("CLAUDE.md", out)

    def test_lower_version_prints_and_a_newer_one_is_silent(self):
        v1 = OLD_BEGIN.replace("begin (", "begin v1 (")
        self.write("AGENTS.md", self.old_block(v1))
        self.write("CLAUDE.md", self.old_block())
        out = self.hook()[1]
        self.assertEqual(len(out.splitlines()), 1, out)
        self.assertIn("rules block in AGENTS.md and CLAUDE.md is older", out)
        self.write("AGENTS.md", self.old_block(OLD_BEGIN.replace("begin (", "begin v999 (")))
        self.write("CLAUDE.md", "@AGENTS.md\n\n" + VIA_IMPORT + "\n")
        self.assert_silent()

    def test_no_repository_and_no_block_are_silent(self):
        outside = os.path.join(self.tmp, "plain folder")
        os.makedirs(outside)
        with open(os.path.join(outside, "AGENTS.md"), "w") as fh:
            fh.write(self.old_block())
        self.assert_silent(cwd=outside)  # no repository around it
        self.assert_silent()  # a repository without rules files
        self.write("AGENTS.md", "# Rules\n\nNothing from the plugin.\n")
        self.write("CLAUDE.md", "@AGENTS.md\n\n" + VIA_IMPORT + "\n")
        self.assert_silent()

    def test_errors_fail_open(self):
        self.write("AGENTS.md", self.old_block())
        self.assertEqual(self.hook()[1].count("\n"), 1, "the block is old")
        for raw in ("not json", "", "[]", "{", '{"cwd": 7}', '{"cwd": null}'):
            code, out, _ = self.hook(raw=raw)
            self.assertEqual((code, out), (0, ""), raw)
        self.assert_silent(cwd=os.path.join(self.tmp, "nowhere"))
        os.remove(os.path.join(self.root, "AGENTS.md"))
        os.makedirs(os.path.join(self.root, "AGENTS.md"))  # a folder, not a file
        with open(os.path.join(self.root, "CLAUDE.md"), "wb") as fh:
            fh.write(b"\xff\xfe not UTF-8 \xff\n")
        self.assert_silent()
        if hasattr(os, "symlink"):
            os.rmdir(os.path.join(self.root, "AGENTS.md"))
            target = os.path.join(self.tmp, "elsewhere.md")
            with open(target, "w") as fh:
                fh.write(self.old_block())
            os.symlink(target, os.path.join(self.root, "AGENTS.md"))
            self.assert_silent()  # a linked rules file is never read

    def test_without_python_it_is_silent(self):
        self.write("AGENTS.md", self.old_block())
        tools = os.path.join(self.tmp, "bin")
        os.makedirs(tools)
        for name in ("sh", "cat"):
            found = shutil.which(name)
            if not found or not hasattr(os, "symlink"):
                self.skipTest("needs sh, cat and symlinks")
            os.symlink(found, os.path.join(tools, name))
        self.env["PATH"] = tools
        self.assert_silent()

    def test_nothing_is_written(self):
        self.write("AGENTS.md", self.old_block())
        self.write("CLAUDE.md", "@AGENTS.md\n")
        scripts = os.path.dirname(CODEMAP)
        before = snapshot(self.tmp), sorted(os.listdir(scripts)), sorted(os.listdir(HERE))
        self.assertEqual(self.hook()[1].count("\n"), 1)
        self.hook(cwd=os.path.join(self.root, "src"), source="clear")
        self.hook(raw="not json")
        after = snapshot(self.tmp), sorted(os.listdir(scripts)), sorted(os.listdir(HERE))
        self.assertEqual(before, after)

    def test_hook_entry(self):
        with open(os.path.join(HERE, "hooks.json")) as fh:
            entries = [e for e in json.load(fh)["hooks"]["SessionStart"]
                       if e.get("matcher") != "compact"]  # that one: test_manager_compaction.py
        self.assertEqual(len(entries), 1)
        self.assertEqual(set(entries[0]["matcher"].split("|")), {"startup", "resume", "clear"})
        entry = entries[0]["hooks"][0]
        self.assertEqual(entry["command"],
                         'sh "${CLAUDE_PLUGIN_ROOT}/hooks/codemap-rules-version.sh"')
        self.assertEqual(entry.get("onFailure"), "continue")
        self.assertLessEqual(entry["timeout"], 10)
        self.assertTrue(os.access(RULES_HOOK, os.X_OK))


def fenced_blocks(path):
    """The fenced code blocks of a markdown file, each as its lines without the fence's indent."""
    blocks, block, indent = [], None, 0
    with open(path, encoding="utf-8") as fh:
        for line in fh.read().split("\n"):
            if line.strip().startswith("```"):
                if block is None:
                    block, indent = [], len(line) - len(line.lstrip())
                else:
                    blocks.append(block)
                    block = None
            elif block is not None:
                block.append(line[indent:] if line[:indent].strip() == "" else line)
    return blocks


def command_in(path, marker):
    found = ["\n".join(b) for b in fenced_blocks(path) if any(marker in line for line in b)]
    assert len(found) == 1, (path, marker, len(found))
    return found[0]


@unittest.skipUnless(shutil.which("awk") and shutil.which("git"), "needs awk and git")
class PlanSectionCommandTest(unittest.TestCase):
    """The briefs' section-only plan read: `git show <base-sha>:<plan-path> | awk ...`
    (the constraints, the binding decisions, the `## Phases` preamble and one phase's section),
    the fallback of `git show <base-sha>:<plan-path> | <python> "<plan.py>" phase <id>`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env = dict(ENV, HOME=self.tmp)
        refs = os.path.join(MANAGER, "references")
        self.command = command_in(os.path.join(refs, "implementer-brief.md"), "awk -v id=<id>")
        self.assertEqual(self.command,
                         command_in(os.path.join(refs, "reviewer-brief.md"), "awk -v id=<id>"),
                         "both briefs give the same command")
        self.assertTrue(self.command.startswith("git show <base-sha>:<plan-path> | awk "))
        self.script = command_in(os.path.join(refs, "implementer-brief.md"), "plan.py")
        self.assertEqual(self.script,
                         command_in(os.path.join(refs, "reviewer-brief.md"), "plan.py"),
                         "both briefs give the same command")

    def git(self, *args):
        p = subprocess.run(["git", "-C", self.tmp] + list(args), check=True,
                           capture_output=True, env=self.env)
        return p.stdout.decode().strip()

    def extract(self, plan_text, phase, command=None):
        """Run the briefs' command (the `awk` one unless another is given), placeholders filled,
        on the plan as committed."""
        if not os.path.isdir(os.path.join(self.tmp, ".git")):
            self.git("init", "-q")
        os.makedirs(os.path.join(self.tmp, "docs"), exist_ok=True)
        with open(os.path.join(self.tmp, "docs", "LIVING PLAN.md"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(plan_text)
        self.git("add", "docs/LIVING PLAN.md")
        self.git("commit", "-qm", "plan", "--allow-empty")
        sha = self.git("rev-parse", "HEAD")
        command = ((command or self.command)
                   .replace("<base-sha>:<plan-path>", '%s:"docs/LIVING PLAN.md"' % sha)
                   .replace("<id>", phase))
        p = subprocess.run(["sh", "-c", command], capture_output=True, env=self.env, cwd=self.tmp)
        self.assertEqual((p.returncode, p.stderr.decode()), (0, ""))
        return p.stdout.decode()

    def test_template_shape(self):
        template = command_in(os.path.join(SKILLS, "living-plan", "references",
                                           "plan-template.md"), "## Binding decisions")
        self.assertIn("### P2. <title>\n...\n", template)
        plan = template.replace(
            "### P2. <title>\n...\n",
            "### P2. Second\nStatus: todo\nObjective: the second thing\n\n"
            "### P10. Tenth\nStatus: todo\nObjective: the tenth thing\n")
        out = self.extract(plan, "P1")
        for kept in ("## Constraints and project rules\n", "- Validation: ", "- Merge: ",
                     "## Binding decisions\n", "- B1. <decision>", "### P1. <title>\n",
                     "Status: todo\n", "Depends on: ", "Risk: ", "Acceptance: ", "Validation: ",
                     "Notes: ", "## Phases\n\nStatus values: `todo` ",
                     "Fix-round limit per phase: 5\n\n### P1. "):
            self.assertIn(kept, out)
        for dropped in ("# <Project>", "## Goal", "## Done means", "## Scope", "## Model strategy",
                        "### P2.", "### P10.", "tenth thing",
                        "## Open owner decisions", "### D1.", "## Decided", "## Notes carried",
                        "## Change log", "## How to keep"):
            self.assertNotIn(dropped, out)
        self.assertEqual(out.count("\n### "), 1)
        self.assertEqual(out.count("Fix-round limit"), 1)
        ten = self.extract(plan, "P10")
        self.assertIn("### P10. Tenth\nStatus: todo\nObjective: the tenth thing\n", ten)
        self.assertNotIn("### P1. ", ten)
        self.assertNotIn("second thing", ten)
        self.assertIn("## Binding decisions\n", ten)
        self.assertIn("Fix-round limit per phase: 5\n\n### P10. ", ten)
        none = self.extract(plan, "plan")  # a plan-only PR's phase id: no phase section
        self.assertNotIn("### ", none)
        self.assertIn("## Constraints and project rules\n", none)
        self.assertIn("- B1. <decision>", none)
        self.assertTrue(none.endswith("Fix-round limit per phase: 5\n\n"), none[-80:])
        self.assertLess(len(out.split()), len(plan.split()) * 0.6)

    def test_sections_under_other_names_are_missing_and_the_briefs_say_what_to_do(self):
        # Only `## Constraints…`, `## Binding decisions` and `## Phases` are known by name; a
        # `###` heading inside a printed section doesn't end it.
        plan = ("# Plan\n\n## Project constraints\n- Validation: `make test`\n\n"
                "## Rules we decided\n- B1. Keep it small.\n\n"
                "## Constraints and project rules\n- Merge: squash\n### Details\n- more\n\n"
                "## Phases\n\nFix-round limit per phase: 3\n\n"
                "### P1. First\nStatus: todo\n\n## Change log\n- created\n")
        out = self.extract(plan, "P1")
        self.assertEqual(out, "## Constraints and project rules\n- Merge: squash\n### Details\n"
                         "- more\n\n## Phases\n\nFix-round limit per phase: 3\n\n"
                         "### P1. First\nStatus: todo\n\n")
        renamed = plan.replace("## Constraints and project rules\n", "## Working agreements\n")
        out = self.extract(renamed, "P1")
        self.assertEqual(out, "## Phases\n\nFix-round limit per phase: 3\n\n"
                         "### P1. First\nStatus: todo\n\n")
        for brief in ("implementer-brief.md", "reviewer-brief.md"):  # the fallback, in prose
            with open(os.path.join(MANAGER, "references", brief), encoding="utf-8") as fh:
                text = " ".join(fh.read().split())
            self.assertRegex(text, r"(?i)no `## Constraints…` or `## Binding decisions` section "
                             r"printed → `grep -n '\^## '` and read them", brief)

    def test_the_plan_script_reads_first_and_the_awk_is_its_fallback(self):
        """`plan.py phase` takes the plan from standard input and no path, so it is still the
        plan as on the base SHA; it prints what the `awk` prints, and the open owner decisions
        and the model-strategy record too. The `awk` stays for a machine without Python."""
        self.assertEqual(self.script,
                         'git show <base-sha>:<plan-path> | <python> "<plan.py>" phase <id>')
        refs = os.path.join(MANAGER, "references")
        script = os.path.join(refs, "..", "..", "living-plan", "scripts", "plan.py")
        self.assertTrue(os.path.isfile(script))
        for brief in ("implementer-brief.md", "reviewer-brief.md"):
            with open(os.path.join(refs, brief), encoding="utf-8") as fh:
                text = " ".join(fh.read().split())
            self.assertIn("``` %s ``` `<plan.py>`: `../../living-plan/scripts/plan.py` from this "
                          "file's folder; `<python>`: `python3`, else `python` or `py -3`. It also "
                          "prints the open owner decisions and the model-strategy record. No "
                          "Python → the same read without those two: ``` git show "
                          "<base-sha>:<plan-path> | awk -v id=<id> '" % self.script, text, brief)
        filled = self.script.replace("<python>", '"%s"' % sys.executable).replace("<plan.py>",
                                                                                  script)
        template = command_in(os.path.join(SKILLS, "living-plan", "references",
                                           "plan-template.md"), "## Binding decisions")
        plan = template.replace("### P2. <title>\n...\n",
                                "### P2. Second\nStatus: todo\nObjective: the second thing\n")
        other = (plan.replace("## Model strategy\n", "## The model strategy\n")
                 .replace("## Open owner decisions\n", "## The open owner decisions\n"))
        for phase in ("P1", "P2"):
            awk, more = self.extract(plan, phase), self.extract(plan, phase, filled)
            for added in ("## Model strategy\n<Written by the manager: ",
                          "## Open owner decisions\n\n### D1. <question>\nBlocks: P<n>\n"):
                self.assertNotIn(added, awk)
                self.assertIn(added, more)
            self.assertIn("### %s. " % phase, more)
            self.assertEqual(more.count("\n### P"), 1)
            self.assertNotIn("## Decided", more)
            # a plan without those two sections: both reads print the same
            self.assertEqual(self.extract(other, phase, filled), self.extract(other, phase))
            self.assertEqual(self.extract(other, phase), awk)

    def test_this_repository_plan(self):
        path = os.path.join(HERE, "..", "..", "..", "docs", "LIVING_PLAN.md")
        if not os.path.isfile(path):
            self.skipTest("no docs/LIVING_PLAN.md beside this plugin copy")
        with open(path, encoding="utf-8") as fh:
            plan = fh.read()
        phases = re.findall(r"(?m)^### (P\d+)\. (.+)$", plan)
        self.assertGreaterEqual(len(phases), 2)
        for phase, title in phases:
            out = self.extract(plan, phase)
            self.assertEqual(re.findall(r"(?m)^### .+$", out), ["### %s. %s" % (phase, title)])
            self.assertEqual(re.findall(r"(?m)^## .+$", out),
                             re.findall(r"(?m)^## (?:Constraints|Binding decisions|Phases).*$",
                                        plan))
            self.assertEqual(len(re.findall(r"(?m)^## .+$", out)), 3)
            body = plan.split("### %s. %s\n" % (phase, title))[1]
            body = re.split(r"(?m)^##", body)[0]
            self.assertIn(body.strip(), out)
            preamble = re.split(r"(?m)^### ", plan.split("\n## Phases\n")[1])[0]
            self.assertIn("Fix-round limit per phase:", preamble)
            self.assertIn("## Phases\n" + preamble, out)
            self.assertLess(len(out.split()), len(plan.split()) * 0.5, phase)


@unittest.skipUnless(shutil.which("awk") and shutil.which("git") and shutil.which("du"),
                     "needs awk, git and du")
class IgnoredDataGuardTest(unittest.TestCase):
    """The manager skill's ignored-data guard command (`references/dispatch.md`): `<entries>
    <KiB>` for the shared checkout."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "check out")
        os.makedirs(self.root)
        self.env = dict(ENV, HOME=self.tmp)
        self.command = command_in(os.path.join(MANAGER, "references", "dispatch.md"),
                                  "--ignored")
        self.assertNotIn("sed -z", self.command)  # GNU-only
        self.assertNotIn("xargs", self.command)

    def write(self, rel, size):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"x" * size)

    def guard(self, cwd=None):
        p = subprocess.run(["sh", "-c", self.command], capture_output=True, env=self.env,
                           cwd=cwd or self.root)
        return p.returncode, p.stdout.decode()

    def du(self, rel):
        p = subprocess.run(["du", "-sk", "--", rel], capture_output=True, env=self.env,
                           cwd=self.root, check=True)
        return int(p.stdout.split()[0])

    def test_counts_ignored_entries_with_spaces_in_their_paths(self):
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True, capture_output=True,
                       env=self.env)
        self.assertEqual(self.guard(), (0, "0 0\n"))
        self.write(".gitignore", 0)
        with open(os.path.join(self.root, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write("data dir/\n*.bin\n-dash/\nd\u00fcnya/\n .lead\n")
        self.write("src/kept file.py", 10)
        self.write("data dir/sub dir/a file.txt", 300000)
        self.write("data dir/b.txt", 5000)
        self.write("big file.bin", 70000)
        self.write("-dash/x", 9000)
        self.write(" .lead", 100)
        entries = ["data dir", "big file.bin", "-dash", " .lead"]
        try:
            self.write("d\u00fcnya/y", 20000)
            entries.append("d\u00fcnya")
        except (OSError, UnicodeError):
            pass
        want = "%d %d\n" % (len(entries), sum(self.du(e) for e in entries))
        self.assertGreater(sum(self.du(e) for e in entries), 300)
        self.assertEqual(self.guard(), (0, want))
        shutil.rmtree(os.path.join(self.root, "data dir"))  # a drop shows in both numbers
        entries.remove("data dir")
        self.assertEqual(self.guard(),
                         (0, "%d %d\n" % (len(entries), sum(self.du(e) for e in entries))))

    def test_outside_a_repository_it_fails_instead_of_printing_zero(self):
        code, out = self.guard(cwd=self.tmp)
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
