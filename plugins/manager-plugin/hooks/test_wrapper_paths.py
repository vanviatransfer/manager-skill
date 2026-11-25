"""The hook wrappers find their Python script from `$0` with either separator: Git Bash on
Windows may start them as `sh C:\\...\\hooks\\scan-guard.sh`, where `${0%/*}` strips nothing.
python3 -m unittest discover -s <this folder>"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402

WRAPPERS = sorted(glob.glob(os.path.join(HERE, "*.sh")))
FINDS_ITS_FOLDER = ("agent-paths.sh", "codemap-commit-check.sh", "codemap-rules-version.sh",
                    "codemap-search-nudge.sh", "manager-context-watch.sh", "scan-guard.sh")
TAKES_ITS_ROOT = ("agent-paths.sh", "codemap-search-nudge.sh", "scan-guard.sh")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def snippet(path):
    """The wrapper's own lines that derive its folder (`here=`) and, where it has one, the plugin
    root (the `case "$root:$0" in` block), as they stand in the file."""
    lines = read(path).splitlines()
    out = [line for line in lines if line.startswith("here=")]
    if 'case "$root:$0" in' in lines:
        start = lines.index('case "$root:$0" in')
        out += ["root=${CLAUDE_PLUGIN_ROOT:-}"] + lines[start:lines.index("esac", start) + 1]
    return "\n".join(out)


def run_sh_file(code, zero, env=None):
    """Stdout of the sh code `code` with the value `zero` in place of `$0`. The code goes in a
    script file with `$0` read as `$1`, and `zero` as that argument: through `sh -c <code>` on
    Windows, the command line's parsing changes the backslashes in `[/\\]` (the snippet then
    split nothing), and a file run with sh can't be given another `$0`."""
    assert "$1" not in code and "${1" not in code
    fd, script = tempfile.mkstemp(suffix=".sh")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code.replace("${0", "${1").replace("$0", "$1") + "\n")
        p = subprocess.run(["sh", script, zero], capture_output=True, env=env)
    finally:
        os.remove(script)
    if p.returncode:
        raise AssertionError(p.stderr.decode())
    return p.stdout.decode()


def run_snippet(path, zero, plugin_root=None):
    """(here, root) after the wrapper's snippet ran with `$0` = zero."""
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    out = run_sh_file(snippet(path) + '\nprintf "%s\\n%s" "$here" "${root-}"', zero, env)
    here, root = out.split("\n")
    return here, root


class SnippetTest(unittest.TestCase):
    """The path-splitting lines themselves, run in sh with Windows- and POSIX-style `$0`."""

    def test_every_wrapper_that_needs_its_folder_has_the_snippet(self):
        names = [os.path.basename(p) for p in WRAPPERS]
        for name in names:
            text = read(os.path.join(HERE, name))
            self.assertNotIn("${0%/*}", text, name)  # `/` only: Windows paths break it
            self.assertEqual(name in FINDS_ITS_FOLDER, "here=${0%[/\\\\]*}" in text, name)
            self.assertEqual(name in TAKES_ITS_ROOT,
                             ":/* | :[A-Za-z]:[/\\\\]* | :\\\\\\\\*) root=\"$here/..\" ;;" in text,
                             name)
            if "$here" in text:
                self.assertIn('script="$here/../skills/', text, name)

    def test_backslash_and_drive_paths(self):
        cases = (
            ("C:\\Users\\o\\plugin\\hooks\\x.sh", "C:\\Users\\o\\plugin\\hooks", True),
            ("c:/Users/o/plugin/hooks/x.sh", "c:/Users/o/plugin/hooks", True),
            ("C:/Users/o/plugin\\hooks\\x.sh", "C:/Users/o/plugin\\hooks", True),
            ("C:\\a b\\plugin\\hooks/x.sh", "C:\\a b\\plugin\\hooks", True),
            ("\\\\server\\share\\plugin\\hooks\\x.sh", "\\\\server\\share\\plugin\\hooks", True),
            ("plugin\\hooks\\x.sh", "plugin\\hooks", False),
            ("C:plugin\\hooks\\x.sh", "C:plugin\\hooks", False),  # drive-relative: no root
        )
        for path in [os.path.join(HERE, n) for n in FINDS_ITS_FOLDER]:
            name = os.path.basename(path)
            for zero, here, absolute in cases:
                got = run_snippet(path, zero.replace("x.sh", name))
                self.assertEqual(got[0], here, (name, zero))
                if name in TAKES_ITS_ROOT:
                    self.assertEqual(got[1], here + "/.." if absolute else "", (name, zero))
                    self.assertEqual(run_snippet(path, zero, "/r")[1], "/r", (name, zero))

    def test_posix_paths_as_before(self):
        """`/` paths give what `${0%/*}` gave, and the root only for an absolute `$0`."""
        for path in [os.path.join(HERE, n) for n in FINDS_ITS_FOLDER]:
            name = os.path.basename(path)
            for zero in ("/home/u/.claude/plugins/m/hooks/" + name, "hooks/" + name,
                         "./" + name, name, "/" + name, "/a b/c'd/hooks/" + name):
                old = run_sh_file('printf %s "${0%/*}"', zero)
                here, root = run_snippet(path, zero)
                self.assertEqual(here, old, (name, zero))
                if name in TAKES_ITS_ROOT:
                    self.assertEqual(root, old + "/.." if zero.startswith("/") else "",
                                     (name, zero))


@unittest.skipIf(portability.WINDOWS, "a file name with \\ in it: POSIX only")
class BackslashZeroTest(unittest.TestCase):
    """The three wrappers that run scan_guard.py and search_nudge.py, started as
    `sh '<tmp>/plugin\\hooks\\<name>.sh'`: a file whose name has backslashes, beside a folder
    literally named `plugin\\hooks`, so the script resolves (through `<tmp>/plugin\\hooks/..`,
    i.e. `<tmp>`, whose `skills` is the plugin's) only when `$0` is split at a backslash."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        os.mkdir(os.path.join(self.tmp, "plugin\\hooks"))
        portability.symlink(self, os.path.join(PLUGIN, "skills"), os.path.join(self.tmp, "skills"))
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, ".codemap.json"), "w", encoding="utf-8") as fh:
            fh.write('{"map": "map.md"}\n')
        with open(os.path.join(self.root, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        state = os.path.join(self.tmp, "state")
        os.mkdir(state)
        self.env = dict(os.environ, TMPDIR=state, TEMP=state, TMP=state, HOME="/home/tester",
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def wrapper(self, name):
        path = os.path.join(self.tmp, "plugin\\hooks\\" + name)
        shutil.copyfile(os.path.join(HERE, name), path)
        return path

    def run_hook(self, path, data, *args):
        p = subprocess.run(["sh", path] + list(args), input=json.dumps(data).encode(),
                           capture_output=True, env=self.env)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def tool(self, name, **tool_input):
        return {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": self.root,
                "hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input}

    def test_scan_guard_runs_its_python_check(self):
        code, _, err = self.run_hook(self.wrapper("scan-guard.sh"),
                                     self.tool("Bash", command="find / -name x"))
        self.assertEqual(code, 2)
        self.assertIn("manager-plugin: scan refused (`find` over `/`)", err)  # scan_guard.py's
        self.assertNotIn("a find over a filesystem root", err)  # not the no-Python fallback
        code, _, err = self.run_hook(self.wrapper("scan-guard.sh"),
                                     self.tool("Grep", pattern="x", path="/"))
        self.assertEqual(code, 2, "Glob and Grep: only scan_guard.py refuses them")

    def test_search_nudge_runs_its_python_check(self):
        code, _, err = self.run_hook(self.wrapper("codemap-search-nudge.sh"),
                                     self.tool("Grep", pattern="foo"))
        self.assertEqual(code, 2)
        self.assertIn("manager-plugin: map first:", err)

    def test_agent_paths_prints_the_start_line(self):
        data = {"session_id": "s", "cwd": self.root, "hook_event_name": "SubagentStart",
                "agent_id": "a1", "agent_type": "manager-plugin:worker"}
        code, out, err = self.run_hook(self.wrapper("agent-paths.sh"), data, "SubagentStart")
        self.assertEqual((code, err), (0, ""))
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("codemap.py", context)
        self.assertIn("skilltrain.py", context)
        self.env["CLAUDE_PLUGIN_ROOT"] = PLUGIN
        code, out, _ = self.run_hook(self.wrapper("agent-paths.sh"), data, "SubagentStart")
        self.assertIn(os.path.join(PLUGIN, "skills", "code-map", "scripts", "codemap.py"),
                      json.loads(out)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
