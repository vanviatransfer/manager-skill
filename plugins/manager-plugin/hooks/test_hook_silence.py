"""The hooks' silence contract, for every command hooks.json registers, run as Claude Code runs it
(`sh -c <command>` with CLAUDE_PLUGIN_ROOT set): with an input its guard does not act on, no
stdout, no stderr, exit 0; a hook that can block (its script exits 2) blocks one input with exit 2
and a message; and no agent-visible text (any probe's output, the blocking messages in the hook
sources) names an environment variable, config key or setting that turns a guard off.
python3 -m unittest discover -s <this folder>"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
SCRIPTS = os.path.join(PLUGIN, "skills", "code-map", "scripts")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
sys.path.insert(0, HERE)
from test_prefer_plugin_agents import CODEMAP, ENV  # noqa: E402
from test_search_nudge import MARKED  # noqa: E402

with open(os.path.join(HERE, "hooks.json"), encoding="utf-8") as _fh:
    HOOKS = json.load(_fh)["hooks"]
# (event, matcher alternative or None, command, timeout) of every registered command.
ENTRIES = [(event, alt, hook["command"], hook.get("timeout", 60))
           for event, groups in sorted(HOOKS.items()) for group in groups
           for alt in (group["matcher"].split("|") if group.get("matcher") else [None])
           for hook in group["hooks"]]
# A tool call no guard acts on, per tool a matcher names.
QUIET_TOOL = {"Bash": {"command": "git status"}, "PowerShell": {"command": "Get-Location"},
              "Grep": {"pattern": "x", "path": "."}, "Glob": {"pattern": "*.py"},
              "Agent": {"subagent_type": "manager-plugin:worker", "description": "d",
                        "prompt": "p"},
              "Task": {"subagent_type": "manager-plugin:worker", "description": "d",
                       "prompt": "p"}}
# What would name a way to turn a guard off: an environment variable, a config key, a settings
# file or an off-switch wording.
OFF_SWITCH = re.compile(
    r"\$\{?[A-Z_][A-Z0-9_]*|\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b|\bsearch_nudge\b|\bcommit_check\b|"
    r"\.codemap\.json|settings(?:\.local)?\.json|disableAllHooks|--no-verify|"
    r"\b(?:disabl\w*|turn\w* (?:\w+ )?off|switch\w* (?:\w+ )?off|off[- ]switch|opt\w*[- ]out|"
    r"bypass\w*|environment variable|env var)\b", re.I)


def script_of(command):
    """`codemap-commit-check.sh` of `sh "${CLAUDE_PLUGIN_ROOT}/hooks/codemap-commit-check.sh"`."""
    return re.search(r"/hooks/([\w.-]+\.sh)", command).group(1)


def blocks(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return bool(re.search(r"^\s*(?:[^#\n]*[;&|]\s*)?exit 2\b", fh.read(), re.M))


def sh_messages(name):
    """The text a hook script itself prints: its here-documents and the quoted printf arguments
    of a line that prints to stderr or right before an `exit 2`."""
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    found, end = [], None
    for line in lines:
        if end is not None:
            if line.strip() == end:
                end = None
            else:
                found.append(line)
            continue
        m = re.search(r"<<-?\s*'?(\w+)'?", line)
        if m and not line.lstrip().startswith("#"):
            end = m.group(1)
    text = "\n".join(lines)
    for m in re.finditer(r"printf '%s(?: %s)*\\n' \\?\n?((?:\s*'[^']*' ?\\?\n?)+)", text):
        found += re.findall(r"'([^']*)'", m.group(1))
    return found


def py_messages(path, functions=None):
    """The string constants of a Python hook script that start a message for the agent (no
    docstrings); with `functions`, only those in the top-level functions of these names."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    tops = [node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name in functions] if functions else [tree]
    docs = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
    return [node.value for top in tops for node in ast.walk(top)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docs and node.value.startswith(("manager-plugin:", "codemap:"))]


@unittest.skipIf(shutil.which("sh") is None, "no sh on PATH: the hooks cannot run here")
class SilenceContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "home")  # no manager-run marker in it
        self.plain = os.path.join(self.tmp, "plain")  # no repository, no plugin marker
        state = os.path.join(self.tmp, "state")
        for folder in (self.home, self.plain, state):
            os.makedirs(folder)
        self.env = dict(ENV, HOME=self.home, TMPDIR=state, TEMP=state, TMP=state,
                        CLAUDE_PLUGIN_ROOT=PLUGIN)
        self.env.pop("USERPROFILE", None)
        self.env.pop("MANAGER_CONTEXT_BUDGET", None)
        self.outputs = []

    def payload(self, event, alt, cwd, tool_input=None):
        data = {"session_id": "s1", "transcript_path": os.path.join(self.tmp, "s1.jsonl"),
                "cwd": cwd, "hook_event_name": event}
        if event == "SessionStart":
            data["source"] = alt
        elif event == "SubagentStart":
            data.update(agent_id="a1", agent_type="manager-plugin:worker")
        elif event == "PreCompact":
            data.update(trigger="auto", custom_instructions="")
        elif event in ("PreToolUse", "PostToolUse"):
            data.update(tool_name=alt, tool_input=tool_input or QUIET_TOOL[alt])
            if event == "PostToolUse":
                data["tool_response"] = {}
        return data

    def run_entry(self, command, data, timeout):
        p = subprocess.run(["sh", "-c", command], input=json.dumps(data).encode(),
                           capture_output=True, env=self.env, cwd=data["cwd"],
                           timeout=timeout * 3)
        out, err = p.stdout.decode(), p.stderr.decode()
        self.outputs.append((script_of(command), out + err))
        return p.returncode, out, err

    def test_every_entry_is_a_plugin_script(self):
        self.assertTrue(ENTRIES)
        for _, _, command, _ in ENTRIES:
            self.assertTrue(os.path.isfile(os.path.join(HERE, script_of(command))), command)
            self.assertTrue(command.startswith('sh "${CLAUDE_PLUGIN_ROOT}/hooks/'), command)

    def test_an_input_no_guard_acts_on_is_silent(self):
        for event, alt, command, timeout in ENTRIES:
            got = self.run_entry(command, self.payload(event, alt, self.plain), timeout)
            self.assertEqual(got, (0, "", ""), (event, alt, command))
        self.assert_no_off_switch()

    def test_each_hook_that_can_block_blocks_with_a_message(self):
        blocking = sorted({script_of(c) for _, _, c, _ in ENTRIES if blocks(script_of(c))})
        self.assertEqual(blocking, sorted(self.blocking_inputs()))
        for event, alt, command, timeout in ENTRIES:
            name = script_of(command)
            probe = self.blocking_inputs().get(name)
            if probe is None or probe[0] != alt:
                continue
            _, cwd, tool_input = probe
            code, out, err = self.run_entry(command, self.payload(event, alt, cwd, tool_input),
                                            timeout)
            self.assertEqual(code, 2, (name, out, err))
            self.assertEqual(out, "", name)
            self.assertTrue(err.strip(), name)
            self.assertTrue(err.startswith(("manager-plugin:", "codemap:")), (name, err))
        self.assertEqual(sorted({n for n, _ in self.outputs}), blocking)
        self.assert_no_off_switch()

    def test_the_search_nudge_skills_branch_blocks_with_a_message(self):
        """The search nudge's second message (skills first), formatted at run time."""
        root = os.path.join(self.tmp, "skills")
        for rel, text in (("docs/vault/skills/notes/records.md", "x\n"),
                          (".claude/skills/notes/SKILL.md", MARKED + "\n## Record\n\n"
                           "Records: `docs/vault/skills/notes/records.md`\n")):
            path = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        os.makedirs(os.path.join(root, ".git"))
        entries = [e for e in ENTRIES if script_of(e[2]) == "codemap-search-nudge.sh"
                   and e[1] == "Grep"]
        self.assertEqual(len(entries), 1)
        event, alt, command, timeout = entries[0]
        code, out, err = self.run_entry(command, self.payload(
            event, alt, root, {"pattern": "lesson", "path": ".claude/skills"}), timeout)
        self.assertEqual((code, out), (2, ""), err)
        self.assertTrue(err.startswith("manager-plugin: skills first: run "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assert_no_off_switch()

    def blocking_inputs(self):
        """{script: (tool, cwd, tool input)} of one input each blocking hook refuses."""
        if not hasattr(self, "_blocking"):
            self._blocking = {
                "prefer-plugin-agents.sh": ("Agent", self.plain, {
                    "subagent_type": "general-purpose", "description": "d", "prompt": "p"}),
                "scan-guard.sh": ("Bash", self.plain, {"command": "find / -name x"}),
                "codemap-search-nudge.sh": ("Grep", self.mapped_repo(), {"pattern": "foo"}),
                "codemap-commit-check.sh": ("Bash", self.stale_repo(),
                                            {"command": "git commit -m x"}),
            }
        return self._blocking

    def mapped_repo(self):
        """A repository with a map, whose first broad search the nudge blocks."""
        root = os.path.join(self.tmp, "mapped")
        os.makedirs(os.path.join(root, ".git"))
        os.makedirs(os.path.join(root, "src"))
        with open(os.path.join(root, ".codemap.json"), "w", encoding="utf-8") as fh:
            fh.write('{"map": "map.md"}\n')
        with open(os.path.join(root, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        return root

    def stale_repo(self):
        """A repository opted in to the commit check, with a staged file its map lacks."""
        root = os.path.join(self.tmp, "stale")
        for rel, text in (("src/app.py", "def run():\n    pass\n"),
                          ("vault/index.md", "- [[map]]\n"),
                          (".codemap.json", '{"vault": "vault", "map": "vault/map.md", '
                                            '"commit_check": true}\n')):
            path = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

        def git(*args):
            subprocess.run(["git", "-C", root] + list(args), check=True, capture_output=True,
                           env=self.env)
        git("init", "-q")
        subprocess.run([sys.executable, CODEMAP, "build", "--root", root], check=True,
                       capture_output=True, env=self.env)
        git("add", "-A")
        git("commit", "-qm", "init")
        with open(os.path.join(root, "src", "new.py"), "w", encoding="utf-8") as fh:
            fh.write("def fresh():\n    pass\n")
        git("add", "-A")
        return root

    def assert_no_off_switch(self):
        """No probe's output names a way to turn a guard off (its own paths aside)."""
        paths = sorted({p for p in (PLUGIN, self.tmp) for p in (p, portability.slashed(p),
                                                                 p.replace("\\", "\\\\"))},
                       key=len, reverse=True)
        for name, text in self.outputs:
            for path in paths:
                text = text.replace(path, "<path>")
            self.assertIsNone(OFF_SWITCH.search(text), (name, text))
            self.assertIsNone(re.search(r"%[sdr(]", text), (name, text))  # formatted in full


class DenialTextTest(unittest.TestCase):
    """The messages in the sources of the hooks that block, checked without running them: none
    names an environment variable, config key or setting that turns the guard off. The prompt
    marker `[general-purpose: <reason>]` that prefer-plugin-agents.sh names is a per-call,
    stated-reason escape, not a setting: it is allowed."""

    def test_messages_name_no_off_switch(self):
        names = sorted({script_of(c) for _, _, c, _ in ENTRIES if blocks(script_of(c))})
        self.assertEqual(names, ["codemap-commit-check.sh", "codemap-search-nudge.sh",
                                 "prefer-plugin-agents.sh", "scan-guard.sh"])
        messages = []
        for name in names:
            messages += [(name, m) for m in sh_messages(name)]
        # codemap.py: only what its hooks.json entries run (claude-hook, session-hook); its git
        # pre-commit hook (`install-hook`, no hooks.json entry) is not in this contract.
        for script, functions in (("codemap.py", ("claude_hook", "session_hook")),
                                  ("scan_guard.py", None), ("search_nudge.py", None)):
            messages += [(script, m) for m in py_messages(os.path.join(SCRIPTS, script),
                                                          functions)]
        self.assertTrue(any("general-purpose is blocked" in m for _, m in messages))
        self.assertTrue(any("scan refused" in m for _, m in messages))
        self.assertTrue(any("map first" in m for _, m in messages))
        self.assertTrue(any("skills first" in m for _, m in messages))
        self.assertTrue(any("code map is stale" in m for _, m in messages))
        for where, text in messages:
            self.assertIsNone(OFF_SWITCH.search(text), (where, text))

    def test_the_pattern_catches_an_off_switch(self):
        for text in ('set "search_nudge": false in .codemap.json', "export SCAN_GUARD_OFF=1",
                     "run with $SKIP_HOOKS", "add disableAllHooks to settings.json",
                     "commit with --no-verify", "to turn this off, ...", "you can disable it"):
            self.assertIsNotNone(OFF_SWITCH.search(text), text)
        for text in ("repeat the search and it will be allowed", "prefix `timeout 120`",
                     'add "[general-purpose: <reason>]" to the prompt', "then commit again"):
            self.assertIsNone(OFF_SWITCH.search(text), text)


if __name__ == "__main__":
    unittest.main()
