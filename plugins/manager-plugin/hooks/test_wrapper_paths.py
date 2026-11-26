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


class RealPathTest(unittest.TestCase):
    """The three wrappers that run scan_guard.py and search_nudge.py, started from where they
    stand as `sh <os.path.join(HERE, name)>` with CLAUDE_PLUGIN_ROOT unset, as the tests and Git
    Bash on Windows start them (there `$0` is `C:\\...\\hooks\\<name>.sh`, which `${0%/*}` leaves
    whole). Each must run its Python check and name the plugin's own scripts. Not skipped
    anywhere: on Windows it covers the backslash `$0`, elsewhere the POSIX one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, ".codemap.json"), "w", encoding="utf-8") as fh:
            fh.write('{"map": "map.md"}\n')
        with open(os.path.join(self.root, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        state = os.path.join(self.tmp, "state")
        os.mkdir(state)
        self.env = dict(os.environ, TMPDIR=state, TEMP=state, TMP=state,
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def run_hook(self, name, data, *args):
        p = subprocess.run(["sh", os.path.join(HERE, name)] + list(args),
                           input=json.dumps(data).encode(), capture_output=True, env=self.env)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def tool(self, name, **tool_input):
        return {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": self.root,
                "hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input}

    def script(self, skill, name):
        """The plugin script's path as the hooks print it (`/` on Windows)."""
        return portability.slashed(os.path.join(PLUGIN, "skills", skill, "scripts", name))

    def test_scan_guard_runs_its_python_check(self):
        code, _, err = self.run_hook("scan-guard.sh", self.tool("Bash", command="find / -name x"))
        self.assertEqual(code, 2, err)
        self.assertIn("manager-plugin: scan refused (`find` over `/`)", err)  # scan_guard.py's
        self.assertNotIn("a find over a filesystem root", err)  # not the no-Python fallback
        self.assertIn('"%s"' % self.script("code-map", "codemap.py"), err)
        code, _, err = self.run_hook("scan-guard.sh", self.tool("Grep", pattern="x", path="/"))
        self.assertEqual(code, 2, "Glob and Grep: only scan_guard.py refuses them")

    def test_search_nudge_runs_its_python_check(self):
        code, _, err = self.run_hook("codemap-search-nudge.sh", self.tool("Grep", pattern="foo"))
        self.assertEqual(code, 2, err)
        self.assertIn("manager-plugin: map first:", err)
        self.assertIn('"%s"' % self.script("code-map", "codemap.py"), err)

    def test_agent_paths_prints_the_start_line(self):
        data = {"session_id": "s", "cwd": self.root, "hook_event_name": "SubagentStart",
                "agent_id": "a1", "agent_type": "manager-plugin:worker"}
        code, out, err = self.run_hook("agent-paths.sh", data, "SubagentStart")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.strip(), "agent-paths.sh printed nothing")
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn('"%s"' % self.script("code-map", "codemap.py"), context)
        self.assertIn('"%s"' % self.script("self-training-skills", "skilltrain.py"), context)


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


@unittest.skipIf(portability.WINDOWS, "sh-script stand-ins for python3, python and py: POSIX only "
                                      "[not verified on Windows]")
class WindowsAppsStubTest(unittest.TestCase):
    """On Windows, `python3` and `python` are often Microsoft Store stubs under
    `...\\Microsoft\\WindowsApps\\` that only fail (exit 9009), slowly. Every wrapper with the Python
    lookup tries such a candidate only after `py -3`, and still tries it last (a Store Python is a
    real one there). Stand-ins on PATH: a stub folder first, a `py` that runs this Python."""

    WRAPPERS = ("agent-paths.sh", "codemap-commit-check.sh", "codemap-rules-version.sh",
                "codemap-search-nudge.sh", "manager-context-watch.sh", "scan-guard.sh")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, ".codemap.json"), "w", encoding="utf-8") as fh:
            fh.write('{"map": "map.md"}\n')
        with open(os.path.join(self.root, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(home, ".claude", "manager-runs", "active"))
        with open(os.path.join(home, ".claude", "manager-runs", "active", "s1"), "w",
                  encoding="utf-8") as fh:
            fh.write("R2026-01-01-0900\n")
        state = os.path.join(self.tmp, "state")
        os.mkdir(state)
        self.log = os.path.join(self.tmp, "ran.log")
        self.env = dict(os.environ, TMPDIR=state, TEMP=state, TMP=state, HOME=home,
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def command(self, folder, name, body):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("#!/bin/sh\necho %s >> '%s'\n%s\n" % (name, self.log, body))
        os.chmod(path, 0o755)

    def path(self, *folders):
        self.env["PATH"] = os.pathsep.join(folders + (os.environ.get("PATH", ""),))

    def ran(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as fh:
            return fh.read().split()

    def inputs(self):
        tool = {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": self.root,
                "hook_event_name": "PreToolUse"}
        return (
            ("agent-paths.sh", {"session_id": "s1", "cwd": self.root,
                                "hook_event_name": "SubagentStart", "agent_id": "a1",
                                "agent_type": "manager-plugin:worker"}, ["SubagentStart"]),
            ("codemap-commit-check.sh", dict(tool, tool_name="Bash",
                                             tool_input={"command": "git commit -m x"}), []),
            ("codemap-rules-version.sh", {"session_id": "s1", "cwd": self.root,
                                          "hook_event_name": "SessionStart"}, []),
            ("codemap-search-nudge.sh", dict(tool, tool_name="Grep",
                                             tool_input={"pattern": "foo"}), []),
            ("manager-context-watch.sh", dict(tool, hook_event_name="PostToolUse",
                                              tool_name="Bash", tool_input={"command": "ls"}),
             []),
            ("scan-guard.sh", dict(tool, tool_name="Bash", tool_input={"command": "ls -la"}), []))

    def run_all(self):
        """{wrapper: (exit code, stdout, stderr, the stand-ins it ran)}, each from a clean log."""
        found = {}
        for name, data, args in self.inputs():
            if os.path.exists(self.log):
                os.remove(self.log)
            p = subprocess.run(["sh", os.path.join(HERE, name)] + args,
                               input=json.dumps(data).encode(), capture_output=True,
                               env=self.env, timeout=60)
            found[name] = (p.returncode, p.stdout.decode(), p.stderr.decode(), self.ran())
        self.assertEqual(sorted(found), sorted(self.WRAPPERS))
        return found

    def test_every_wrapper_with_the_lookup_is_covered(self):
        for path in WRAPPERS:
            name = os.path.basename(path)
            self.assertEqual('for c in python3 python "py -3"' in read(path),
                             name in self.WRAPPERS, name)

    def test_a_windowsapps_stub_is_never_run_when_py_works(self):
        stubs = os.path.join(self.tmp, "Users", "o", "AppData", "Local", "Microsoft", "WindowsApps")
        for name in ("python3", "python"):
            self.command(stubs, name, "sleep 2\nexit 49")  # 9009, as an exit status
        self.command(os.path.join(self.tmp, "launcher"), "py",
                     '[ "$1" = -3 ] || exit 3\nshift\nexec "%s" "$@"' % sys.executable)
        self.path(stubs, os.path.join(self.tmp, "launcher"))
        found = self.run_all()
        for name, (code, out, err, ran) in found.items():
            self.assertEqual(ran, ["py"], (name, code, out, err))
        self.assertEqual(found["codemap-search-nudge.sh"][0], 2)
        self.assertIn("manager-plugin: map first:", found["codemap-search-nudge.sh"][2])
        self.assertIn("hookSpecificOutput", found["agent-paths.sh"][1])
        self.assertEqual(found["scan-guard.sh"][:3], (0, "", ""))

    def test_a_store_python_under_windowsapps_still_runs_last(self):
        if shutil.which("py", path=os.environ.get("PATH", "")):
            self.skipTest("a real `py` on PATH")
        stubs = os.path.join(self.tmp, "AppData", "Local", "Microsoft", "WINDOWSAPPS")
        self.command(stubs, "python3", 'exec "%s" "$@"' % sys.executable)
        self.command(stubs, "python", "exit 49")
        self.path(stubs)
        found = self.run_all()
        for name, (code, out, err, ran) in found.items():
            self.assertEqual(ran, ["python3"], (name, code, out, err))
        self.assertEqual(found["codemap-search-nudge.sh"][0], 2)
        self.assertIn("hookSpecificOutput", found["agent-paths.sh"][1])
        self.assertEqual(found["scan-guard.sh"][:3], (0, "", ""))

    def test_a_python_elsewhere_runs_first_as_before(self):
        folder = os.path.join(self.tmp, "usr", "bin")
        self.command(folder, "python3", 'exec "%s" "$@"' % sys.executable)
        self.command(os.path.join(self.tmp, "launcher"), "py", "exit 3")
        self.path(folder, os.path.join(self.tmp, "launcher"))
        for name, (code, out, err, ran) in self.run_all().items():
            self.assertEqual(ran, ["python3"], (name, code, out, err))


if __name__ == "__main__":
    unittest.main()
