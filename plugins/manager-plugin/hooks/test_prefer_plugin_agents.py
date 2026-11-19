"""Tests for the plugin hooks (prefer-plugin-agents.sh, codemap-commit-check.sh):
python3 -m unittest discover -s <this folder>"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "prefer-plugin-agents.sh")
COMMIT_HOOK = os.path.join(HERE, "codemap-commit-check.sh")
CODEMAP = os.path.join(HERE, "..", "skills", "code-map", "scripts", "codemap.py")
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


if __name__ == "__main__":
    unittest.main()
