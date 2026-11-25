"""Tests for scan-guard.sh, agent-paths.sh and scan_guard.py: whole-disk scans refused, the
timeout hint, and the start-context line with the plugin's script paths:
python3 -m unittest discover -s <this folder>"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "scan-guard.sh")
PATHS = os.path.join(HERE, "agent-paths.sh")
NUDGE = os.path.join(HERE, "codemap-search-nudge.sh")
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
SCRIPTS = os.path.join(PLUGIN, "skills", "code-map", "scripts")
sys.dont_write_bytecode = True
sys.path.insert(0, SCRIPTS)
import scan_guard  # noqa: E402
import search_nudge  # noqa: E402

FAKE_HOME = "/home/tester"
CWD = "/home/tester/proj"

# Bash commands refused from CWD.
BLOCK_BASH = [
    "find / -name codemap.py -path '*manager*'",
    "find -L / -name x", "find . / -name x", "find -H -- / -name x", "find / -type f",
    # Git Bash, Cygwin and WSL drive roots, any letter and case
    "find /c -name x", "find /c/ -name x", "find /C -name x", "find /d/ -name x",
    "find /cygdrive/c -name x", "find /mnt/c -name x", "find /mnt/D/ -name x",
    # Windows spellings
    "find C:/ -name x", "find C:\\ -name x", "find c: -name x", "find C:\\\\ -name x",
    "find 'C:\\' -name x", 'find "C:\\\\" -name x', "find 'c:/' -name x",
    "find 'C:\\Users' -name x", "find C:\\Users -name x", "find /c/Users -name x",
    # home
    "find ~ -name x", "find ~/ -name x", "find $HOME -name x", "find ${HOME} -name x",
    'find "$HOME" -name x', "find $HOME/ -name x", "find /home -name x", "find /Users -name x",
    "find /root -name x", "find %s -name x" % FAKE_HOME, "find ../.. -name x",
    "find /* -name x",
    # other recursive scans
    "ls -R /", "ls -lR ~", "ls -Ra C:/", "ls --recursive /home", "du /", "du -sh ~",
    "du -sh /c/", "tree /", "tree ~", "grep -r foo /", "grep -R foo ~", "grep --recursive foo /",
    "grep -rn foo /", "egrep -r foo $HOME", "rg foo /", "rg --files /", "rg foo C:/", "ag foo /",
    "ack foo ~", "fd codemap.py /", "fd -t f x ~", "fd x --search-path /",
    # wrappers
    'bash -c "find / -name x"', "sh -c 'find / -name x'", "bash -lc 'ls -R /'",
    "bash -o pipefail -c 'rg foo /'", 'powershell -Command "Get-ChildItem C:\\ -Recurse"',
    "pwsh -c 'gci ~ -r'", "powershell.exe -NoProfile -Command \"gci -Path 'C:\\' -Recurse\"",
    "cmd /c dir /s C:\\", "cmd //c dir //s C:\\\\", "cmd.exe /c \"dir /s/b C:\\\"",
    "echo x | find / -name x", "true && find / -name x", "false || find / -name x",
    "cd src; find / -name x", "(find / -name x)", "echo $(find / -name x)",
    "echo `find / -name x`", 'echo "$(find / -name x)"', 'x="`ls -R /`"',
    "timeout 120 find / -name x", "sudo find / -name x", "nice -n 5 du -sh /",
    "env LC_ALL=C grep -r foo /", "FOO=1 find / -name x", "find / -name x 2>/dev/null | head",
    # implicit path, the cwd moved to a root first
    "cd / && find . -name x", "cd ~ && rg foo", "cd && grep -r foo .", "cd C:/ && ls -R",
    # unparseable (unbalanced quote): the token check still sees find on a root
    "find / -name 'x",
]
# Bash commands allowed from CWD.
PASS_BASH = [
    "find . -name x", "find scripts -type f", 'find "$REPO" -name x',
    "find /home/u/proj -name x", "find ~/proj", "find ~/.claude/plugins -name codemap.py",
    "find /tmp -name x", "find C:/Users/me/proj -name x", "find / -maxdepth 1",
    "find / -maxdepth 0 -name x", "find --help", "rg foo src", "rg foo", "grep -rn foo src",
    "grep -r foo .", "du -sh node_modules", "ls -la /", "ls /", "ls ~", "grep x /etc/hosts",
    "tree -L 1 /", "tree src", "ls -R ~/proj", "du -sh ~/proj", "git grep foo",
    "echo 'find / -name x'", "grep -rn 'find /' src", "echo find / > notes.txt",
    "printf '%s' 'rg foo /' | wc", "cat <<'EOF'\nfind / -name x\nEOF",
    "git commit -m \"$(cat <<'EOF'\nfind / -name x\nEOF\n)\"",
    "cd /tmp && find . -name x", "cd / && ls", "cd ~ && ls -la", "locate codemap.py",
    "find \"unbalanced / -name x", "bash script.sh /", "cat / 2>&1",
    "python3 -m unittest discover -s hooks", "rg -n foo -- /home/u/proj",
    # cmd's find.exe and tree.com: /x are switches
    'cmd /c find /i "x" file', 'cmd //c find //c "x" file.txt', "cmd /c tree /f",
]
# PowerShell commands refused from a Windows cwd.
BLOCK_PS = [
    "Get-ChildItem C:\\ -Recurse", "gci -r C:/", "dir -rec C:", "ls -Recurse \\",
    "Get-ChildItem / -Recurse", "gci ~ -Recurse", "gci $HOME -Recurse",
    "gci $env:USERPROFILE -Recurse -Filter codemap.py", "gci $env:HOMEDRIVE\\ -Recurse",
    "gci ${env:USERPROFILE} -Recurse", "GET-CHILDITEM c:\\ -RECURSE", "gci -R C:\\",
    "Get-ChildItem -Path C:\\ -Recurse -Filter x", "Get-ChildItem -Path:C:\\ -Recurse",
    "Get-ChildItem -LiteralPath 'C:\\' -Recurse", "Get-ChildItem -Filter x -Path C:\\ -Recurse",
    "Get-ChildItem C:\\ -Depth 5", "gci 'C:\\Users' -Recurse", "gci D:\\ -Recurse | select -f 1",
    "cmd /c dir /s C:\\", "cmd /c \"dir C:\\ /s\"", "cd C:\\; gci -Recurse",
    "Set-Location ~; Get-ChildItem -Recurse", "$x = gci C:\\ -Recurse", "& gci C:\\ -Recurse",
    "powershell -Command \"gci C:\\ -Recurse\"", "pwsh -c 'gci ~ -r'",
    "bash -c 'find / -name x'", "rg foo C:\\", "where.exe /r C:\\ codemap.py",
    "1..2 | ForEach-Object { gci C:\\ -Recurse }", "tree C:\\ /f", "cmd /c tree C:\\ /f",
    "find / ", "gci C:\\ -Depth 2", "Get-ChildItem C:\\ -Recurse -Depth 5",
]
PASS_PS = [
    "Get-ChildItem -Recurse .\\scripts", "gci C:\\", "Get-ChildItem C:\\ -Filter *.txt",
    "gci -Recurse C:\\Users\\me\\proj", "gci -Recurse", "Get-ChildItem -Recurse -Path src",
    "Write-Output 'gci C:\\ -Recurse'", "rg foo src", "dir", "ls -la /",
    # find.exe and tree.com switches are no Git Bash drive roots; /c is no root here
    "tree /f", "tree /f /a", 'tasklist | find /i "python"', 'find /c "x" file.txt',
    'find /v /n "x" a.txt', "find /?", 'cmd /c find /i "x" file', "cmd /c tree /f",
    "gci /c -Recurse", "rg foo /c", "Get-ChildItem C:\\ -Depth 0", "gci C:\\ -Depth 1",
    "gci -Depth:1 C:\\", "Get-ChildItem -Recurse -Depth 1 C:\\",
]
WIN_CWD = "C:\\Users\\me\\proj"


def refused(tool, cwd=CWD, **tool_input):
    return scan_guard.refused({"session_id": "s", "cwd": cwd, "hook_event_name": "PreToolUse",
                               "tool_name": tool, "tool_input": tool_input})


class PredicateTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"HOME": FAKE_HOME})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("USERPROFILE", None)

    def test_bash_table(self):
        for cmd in BLOCK_BASH:
            self.assertIsNotNone(refused("Bash", command=cmd), cmd)
        for cmd in PASS_BASH:
            self.assertIsNone(refused("Bash", command=cmd), cmd)

    def test_powershell_table(self):
        for cmd in BLOCK_PS:
            self.assertIsNotNone(refused("PowerShell", cwd=WIN_CWD, command=cmd), cmd)
        for cmd in PASS_PS:
            self.assertIsNone(refused("PowerShell", cwd=WIN_CWD, command=cmd), cmd)

    def test_cwd_root_makes_an_implicit_path_a_root_scan(self):
        for cwd in ("/", "C:\\", "c:/", "/c", "/home", FAKE_HOME, "/Users", "C:\\Users"):
            for cmd in ("find . -name x", "find -name x", "rg foo", "grep -r foo .", "ls -R",
                        "du -sh", "tree", "fd x"):
                self.assertIsNotNone(refused("Bash", cwd=cwd, command=cmd), (cwd, cmd))
            ps = refused("PowerShell", cwd=cwd, command="gci -Recurse")
            if cwd == "/c":  # a Git Bash spelling: in PowerShell, a folder of the current drive
                self.assertIsNone(ps, cwd)
            else:
                self.assertIsNotNone(ps, cwd)
            self.assertIsNotNone(refused("Grep", cwd=cwd, pattern="x"), cwd)
            self.assertIsNotNone(refused("Glob", cwd=cwd, pattern="**/x"), cwd)
            self.assertIsNone(refused("Bash", cwd=cwd, command="find src -name x"), cwd)
            self.assertIsNone(refused("Bash", cwd=cwd, command="ls -la"), cwd)
            self.assertIsNone(refused("Bash", cwd=cwd, command="rg foo proj"), cwd)

    def test_glob_and_grep(self):
        for path in ("/", "C:\\", "C:/", "c:", "/c/", "~", "$HOME", "/home", "/Users", FAKE_HOME):
            self.assertIsNotNone(refused("Grep", pattern="x", path=path), path)
            self.assertIsNotNone(refused("Glob", pattern="*.py", path=path), path)
        for pattern in ("/**/x", "C:/**/x", "C:\\**\\codemap.py", "~/**/x", "/home/**/x",
                        "$HOME/**/codemap.py", "../../**/x"):
            self.assertIsNotNone(refused("Glob", pattern=pattern), pattern)
        for ti in ({"pattern": "x"}, {"pattern": "x", "path": "src"},
                   {"pattern": "x", "path": "/home/u/proj"}, {"pattern": "x", "path": "~/proj"}):
            self.assertIsNone(refused("Grep", **ti), ti)
        for ti in ({"pattern": "**/*.py"}, {"pattern": "src/**"}, {"pattern": "/etc/*.conf"},
                   {"pattern": "/home/u/proj/**/x"}, {"pattern": "~/.claude/plugins/**/x"},
                   {"pattern": "*.py", "path": "/home/u/proj"}, {"pattern": "/*"}):
            self.assertIsNone(refused("Glob", **ti), ti)

    def test_home_that_is_a_repository_top_is_no_root(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        app = os.path.join(tmp, "app")
        os.makedirs(os.path.join(app, "src"))
        with mock.patch.dict(os.environ, {"HOME": app}):
            self.assertIsNotNone(refused("Bash", command="find %s -name x" % app), "no repo")
            os.makedirs(os.path.join(app, ".git"))
            for cmd in ("find %s -name x" % app, "rg foo %s" % app):
                self.assertIsNone(refused("Bash", cwd=app, command=cmd), cmd)
            self.assertIsNone(refused("Bash", cwd=app, command="find . -name x"))
            self.assertIsNone(refused("Grep", cwd=app, pattern="x"))
            self.assertIsNotNone(refused("Bash", cwd=app, command="find ~ -name x"),
                                 "the ~ spelling stays a root")
            sub = os.path.join(app, "src")
            with mock.patch.dict(os.environ, {"HOME": sub}):
                self.assertIsNotNone(refused("Bash", command="find %s -name x" % sub),
                                     "inside a repository but not its top: still a root")

    def test_other_tools_and_bad_input_pass(self):
        self.assertIsNone(refused("Read", file_path="/"))
        self.assertIsNone(scan_guard.refused("not a dict"))
        self.assertIsNone(scan_guard.refused({"tool_name": "Bash", "tool_input": "x"}))
        self.assertIsNone(refused("Bash", command=None))
        self.assertEqual(scan_guard.main.__name__, "main")


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.state)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "src"))
        self.env = dict(os.environ, TMPDIR=self.state, TEMP=self.state, TMP=self.state,
                        PYTHONDONTWRITEBYTECODE="1", HOME=FAKE_HOME, CLAUDE_PLUGIN_ROOT=PLUGIN)
        self.env.pop("USERPROFILE", None)
        self.session = "s1"

    def data(self, tool, cwd=None, **tool_input):
        return json.dumps({"session_id": self.session, "transcript_path": "/t/s.jsonl",
                           "cwd": cwd or self.root, "hook_event_name": "PreToolUse",
                           "tool_name": tool, "tool_input": tool_input})

    def run_sh(self, script, data, env=None, args=(), sh="sh"):
        p = subprocess.run([sh, script] + list(args), input=data.encode(), capture_output=True,
                           env=env or self.env)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def guard(self, tool, **kw):
        return self.run_sh(GUARD, self.data(tool, **kw))

    def expected(self, name, path):
        top = self.root.replace("\\", "/")
        code = os.path.join(PLUGIN, "skills", "code-map", "scripts", "codemap.py")
        skill = os.path.join(PLUGIN, "skills", "self-training-skills", "scripts", "skilltrain.py")
        return ('manager-plugin: scan refused (`%s` over `%s`): a recursive scan of a filesystem, '
                'drive or home root can run for hours and exhaust memory. Code map: `python3 "%s" '
                'query <term> --root "%s"`; skill files: `python3 "%s" query "%s" -- <term>`; or '
                'search only the repository: `rg <term> "%s"` or `find "%s" -name <x>` (prefix '
                '`timeout 120` for a long one). Never search for these scripts: their paths come '
                'here and at session and agent start.'
                % (name, path, code, top, skill, top, top, top))

    def test_block_message(self):
        code, out, err = self.guard("Bash", command="find / -name codemap.py -path '*manager*'")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.strip(), self.expected("find", "/"))
        code, out, err = self.guard("PowerShell", command="Get-ChildItem C:\\ -Recurse")
        self.assertEqual(code, 2)
        self.assertEqual(err.strip(), self.expected("get-childitem", "C:\\"))
        code, _, err = self.guard("Glob", pattern="/**/codemap.py")
        self.assertEqual(code, 2)
        self.assertEqual(err.strip(), self.expected("Glob", "/"))

    def test_block_message_without_a_plugin_root(self):
        self.env["CLAUDE_PLUGIN_ROOT"] = os.path.join(self.tmp, "missing")
        code, _, err = self.guard("Bash", command="find / -name x")
        self.assertEqual(code, 2)
        self.assertIn("Code map: the `manager-plugin:code-map` skill's `query <term>`; skill "
                      "files: the `manager-plugin:self-training-skills` skill's `skilltrain.py "
                      "query <repo root> -- <term>`;", err)
        self.assertTrue(err.strip().endswith(
            "Never search for these scripts: their paths come at session and agent start."), err)
        self.assertNotIn("come here", err)

    def test_block_message_outside_a_repository(self):
        code, _, err = self.guard("Bash", cwd="/", command="find . -name x")
        self.assertEqual(code, 2)
        self.assertIn("`rg <term> <repo path>` or `find <repo path> -name <x>`", err)
        self.assertIn('query <repo root> -- <term>', err)

    def test_wrapped_and_root_cases_through_the_hook(self):
        for cmd in ('bash -c "find / -name x"', "cmd //c dir //s C:\\\\", "echo $(ls -R ~)",
                    "find C:\\ -name x", "du -sh /c/"):
            self.assertEqual(self.guard("Bash", command=cmd)[0], 2, cmd)
        self.assertEqual(self.guard("Grep", cwd="/", pattern="x")[0], 2)
        for cmd in ("find . -name x", "ls -la /", "echo hi"):
            self.assertEqual(self.guard("Bash", command=cmd)[0], 0, cmd)

    def test_timeout_hint_once(self):
        code, out, err = self.guard("Bash", command="find . -name x")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "manager-plugin: long recursive scans: prefix `timeout 120`."}})
        self.assertNotIn("permissionDecision", out)
        for cmd in ("find . -name x", "rg foo src", "grep -r foo ."):
            self.assertEqual(self.guard("Bash", command=cmd), (0, "", ""), "once per session")
        self.session = "s2"
        for cmd in ("timeout 120 find . -name x", "timeout -k 5 60 rg foo", "ls -la", "echo find",
                    "grep foo README.md", "find . -maxdepth 1"):
            self.assertEqual(self.guard("Bash", command=cmd), (0, "", ""), cmd)
        self.assertEqual(self.guard("PowerShell", command="gci -Recurse src"), (0, "", ""))
        self.assertEqual(self.guard("Grep", pattern="x"), (0, "", ""))
        self.assertIn("timeout 120", self.guard("Bash", command="ls -R src")[1])
        self.assertEqual(self.guard("Bash", command="du -sh src"), (0, "", ""))

    def test_hint_ignores_search_nudge_off(self):
        with open(os.path.join(self.root, ".codemap.json"), "w") as fh:
            fh.write('{"map": "map.md", "search_nudge": false}\n')
        self.assertEqual(self.guard("Bash", command="find / -name x")[0], 2, "no off switch")

    def nopy_env(self, tools=("cat", "grep")):
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        for t in tools:
            path = shutil.which(t)
            if path and not os.path.exists(os.path.join(bin_dir, t)):
                os.symlink(path, os.path.join(bin_dir, t))
        return dict(self.env, PATH=bin_dir)

    @unittest.skipUnless(os.path.exists("/bin/sh") and hasattr(os, "symlink"), "POSIX")
    def test_fallback_without_python(self):
        env = self.nopy_env()
        msg = ("manager-plugin: scan refused: a find over a filesystem root, drive root or home "
               "folder can run for hours and exhaust memory; search only the repository "
               "instead: `rg <term> <repo path>` or `find <repo path> -name <x>` (`timeout 120` "
               "in front of a long one).")
        for cmd in ("find / -name x", "find /", "find -L / -name x", "find -H -- / -name x",
                    "find C:\\ -name x", "find C:\\\\ -name x", "find c: -name x",
                    "find C:/ -name x", "find /c/ -name x", "find /cygdrive/c -name x",
                    "find /mnt/c -name x", "find ~ -name x", "find ~/ -name x",
                    "find $HOME -name x", "find ${HOME} -name x", 'find "$HOME" -name x',
                    "find /home -name x", "find /Users", "find /root -name x",
                    "find 'C:\\Users' -name x", "cd x && find / -name x"):
            code, out, err = self.run_sh(GUARD, self.data("Bash", command=cmd), env, sh="/bin/sh")
            self.assertEqual((code, err.strip()), (2, msg), cmd)
        for cmd in ("find . -name x", "find /home/u/proj -name x", "find ~/proj",
                    "find ~/.claude/plugins -name codemap.py", "find . /", "ls -R /",
                    "rg foo /", "find /tmp", "echo hi"):
            code, out, err = self.run_sh(GUARD, self.data("Bash", command=cmd), env, sh="/bin/sh")
            self.assertEqual((code, out, err), (0, "", ""), cmd)
        code, _, _ = self.run_sh(GUARD, self.data("Grep", cwd="/", pattern="x"), env, sh="/bin/sh")
        self.assertEqual(code, 0, "no Python: Glob and Grep fail open")
        compact = json.dumps(json.loads(self.data("Bash", command="find / -name x")),
                             separators=(",", ":"))
        self.assertEqual(self.run_sh(GUARD, compact, env, sh="/bin/sh")[0], 2, "no spaces")
        for tool, cmd in (("PowerShell", 'tasklist | find /i "py"'), ("PowerShell", "find /"),
                          ("Bash", "echo find / x"), ("Bash", 'echo "find / -x"'),
                          ("Bash", "grep -n 'find /' notes")):
            for sep in ((", ", ": "), (",", ":")):
                data = json.dumps(json.loads(self.data(tool, command=cmd)), separators=sep)
                self.assertEqual(self.run_sh(GUARD, data, env, sh="/bin/sh"), (0, "", ""),
                                 (tool, cmd))
        for sep in ((", ", ": "), (",", ":")):
            data = json.dumps({"session_id": "s", "cwd": "/x", "tool_name": "Bash",
                               "tool_input": {"command": "rg foo src",
                                              "description": "not a find / scan"}},
                              separators=sep)
            self.assertEqual(self.run_sh(GUARD, data, env, sh="/bin/sh"), (0, "", ""),
                             "the description field is never matched")
        for cmd in ("cd x && find / -name x", "echo $(find / -name x)", "a; find ~ -name x",
                    "echo x |find / -name x"):
            code, _, _ = self.run_sh(GUARD, self.data("Bash", command=cmd), env, sh="/bin/sh")
            self.assertEqual(code, 2, cmd)
        env = self.nopy_env(())
        env["PATH"] = os.path.join(self.tmp, "empty")
        code, _, _ = self.run_sh(GUARD, self.data("Bash", command="find / -name x"), env,
                                 sh="/bin/sh")
        self.assertEqual(code, 0, "no grep either: fail open")

    def test_nudge_state_not_used_by_a_refused_command(self):
        with open(os.path.join(self.root, ".codemap.json"), "w") as fh:
            fh.write('{"map": "map.md"}\n')
        open(os.path.join(self.root, "src", "a.py"), "w").close()
        cmd = "find / -name x; grep -r foo ."  # refused, and broad for the nudge
        self.assertEqual(self.run_sh(GUARD, self.data("Bash", command=cmd))[0], 2)
        self.assertEqual(self.run_sh(NUDGE, self.data("Bash", command=cmd))[0], 0)
        code, _, err = self.run_sh(NUDGE, self.data("Bash", command="grep -r foo ."))
        self.assertEqual(code, 2, "the nudge's block is still there")
        self.assertIn("map first", err)
        # Without the guard's predicate the nudge would have used its block on that command.
        self.session = "s3"
        data = json.loads(self.data("Bash", command=cmd))
        env = {"TMPDIR": self.state, "TEMP": self.state, "TMP": self.state}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(scan_guard, "refused", return_value=None):
            self.assertEqual(search_nudge.run(data), 2)

    def start(self, event="SubagentStart", cwd=None, env=None):
        data = json.dumps({"session_id": "s", "cwd": cwd or self.root, "hook_event_name": event,
                           "agent_id": "a1", "agent_type": "manager-plugin:worker"})
        code, out, err = self.run_sh(PATHS, data, env=env, args=[event])
        self.assertEqual((code, err), (0, ""))
        return json.loads(out)["hookSpecificOutput"] if out else None

    def start_line(self):
        top = self.root.replace("\\", "/")
        code = os.path.join(PLUGIN, "skills", "code-map", "scripts", "codemap.py")
        skill = os.path.join(PLUGIN, "skills", "self-training-skills", "scripts", "skilltrain.py")
        return ('manager-plugin: the plugin\'s scripts, runnable as given (never search the disk '
                'for these): code map `python3 "%s" query <term> --root "%s"`; skill files '
                '`python3 "%s" query "%s" -- <term>`.' % (code, top, skill, top))

    def test_start_line_needs_the_condition(self):
        self.assertIsNone(self.start(), "a repository without the plugin's marks")
        self.assertIsNone(self.start("SessionStart"))
        self.assertIsNone(self.start(cwd=self.tmp), "no repository")

    def test_start_line_with_a_codemap_config(self):
        open(os.path.join(self.root, ".codemap.json"), "w").close()
        for event in ("SubagentStart", "SessionStart"):
            out = self.start(event, cwd=os.path.join(self.root, "src"))
            self.assertEqual(out, {"hookEventName": event, "additionalContext": self.start_line()})
        self.env["CLAUDE_PLUGIN_ROOT"] = os.path.join(self.tmp, "missing")
        self.assertIsNone(self.start(), "no runnable command: nothing to say")

    def test_start_line_with_a_rules_marker_or_a_marked_skill(self):
        path = os.path.join(self.root, "CLAUDE.md")
        with open(path, "w") as fh:
            fh.write("# x\n<!-- manager-plugin:code-map:begin v2 (managed by the code-map skill)"
                     " -->\n")
        self.assertEqual(self.start()["additionalContext"], self.start_line())
        with open(path, "w") as fh:
            fh.write("- use skilltrain <!-- manager-plugin:self-training-skills -->\n")
        self.assertEqual(self.start()["additionalContext"], self.start_line())
        os.remove(path)
        self.assertIsNone(self.start())
        skill = os.path.join(self.root, ".claude", "skills", "deploy")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w") as fh:
            fh.write("---\nname: deploy\ndescription: x\n---\n<!-- self-training-skill v1 -->\n")
        self.assertEqual(self.start()["additionalContext"], self.start_line())

    def test_start_line_without_git_finds_the_config(self):
        shutil.rmtree(os.path.join(self.root, ".git"))
        open(os.path.join(self.root, ".codemap.json"), "w").close()
        out = self.start(cwd=os.path.join(self.root, "src"))
        self.assertEqual(out["additionalContext"], self.start_line())

    def test_hook_entries(self):
        with open(os.path.join(HERE, "hooks.json")) as fh:
            hooks = json.load(fh)["hooks"]
        guard = [e for e in hooks["PreToolUse"] if "scan-guard.sh" in e["hooks"][0]["command"]]
        self.assertEqual(len(guard), 1)
        self.assertEqual(set(guard[0]["matcher"].split("|")), {"Bash", "PowerShell", "Glob", "Grep"})
        sub = hooks["SubagentStart"]
        self.assertEqual(len(sub), 1)
        self.assertNotIn("matcher", sub[0], "every agent type")
        start = [e for e in hooks["SessionStart"] if "agent-paths.sh" in e["hooks"][0]["command"]]
        self.assertEqual(len(start), 1)
        self.assertEqual(set(start[0]["matcher"].split("|")),
                         {"startup", "resume", "clear", "compact"})
        for entry, event in ((guard[0], None), (sub[0], "SubagentStart"),
                             (start[0], "SessionStart")):
            hook = entry["hooks"][0]
            self.assertEqual(hook.get("onFailure"), "continue")
            if event:
                self.assertEqual(hook["command"],
                                 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/agent-paths.sh" ' + event)


if __name__ == "__main__":
    unittest.main()
