"""Tests for codemap-search-nudge.sh and search_nudge.py, the "map first" hook:
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
HOOK = os.path.join(HERE, "codemap-search-nudge.sh")
SCRIPTS = os.path.join(HERE, "..", "skills", "code-map", "scripts")
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, SCRIPTS)
import search_nudge  # noqa: E402

CONFIG = '{"vault": "vault", "map": "vault/map.md"}\n'


class SearchNudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "repo")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.state)
        self.env = dict(os.environ, TMPDIR=self.state, TEMP=self.state, TMP=self.state,
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)  # the wrapper's own folder then
        for rel in ("src/pkg/mod.py", "src/app.py", "vault/index.md", "vault/map.md",
                    "vault/map/src.md", "README.md"):
            self.write(rel, "x\n")
        self.write(".codemap.json", CONFIG)
        os.makedirs(os.path.join(self.root, ".git"))
        self.session = "s1"

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="\n") as fh:
            fh.write(text)

    def hook(self, tool, cwd=None, raw=None, **tool_input):
        data = raw if raw is not None else json.dumps(
            {"session_id": self.session, "transcript_path": "/t/%s.jsonl" % self.session,
             "cwd": cwd or self.root, "hook_event_name": "PreToolUse", "tool_name": tool,
             "tool_input": tool_input})
        p = subprocess.run(["sh", HOOK], input=data.encode(), capture_output=True, env=self.env)
        return p.returncode, p.stderr.decode()

    def bash(self, command, **kw):
        return self.hook("Bash", command=command, **kw)[0]

    def assert_first_blocked(self, tool, **tool_input):
        code, err = self.hook(tool, **tool_input)
        self.assertEqual(code, 2, (tool, tool_input))
        self.assertEqual(len(err.strip().splitlines()), 1)
        script = os.path.join(PLUGIN, "skills", "code-map", "scripts", "codemap.py")
        self.assertIn('run python3 "%s" query <term> (or read' % script, err)
        self.assertIn("vault/map.md", err)
        self.assertEqual(self.hook(tool, **tool_input)[0], 0, "a repeat is allowed")

    def test_message_names_the_plugin_root_command(self):
        plugin = os.path.join(self.tmp, "my plugins", "manager-plugin")
        os.makedirs(os.path.join(plugin, "skills", "code-map", "scripts"))
        open(os.path.join(plugin, "skills", "code-map", "scripts", "codemap.py"), "w").close()
        self.env["CLAUDE_PLUGIN_ROOT"] = plugin
        code, err = self.hook("Grep", pattern="foo")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn('manager-plugin: map first: run python3 "%s/skills/code-map/scripts/'
                      'codemap.py" query <term> (or read the vault index or the map page '
                      'vault/map.md) before a broad search;' % plugin, err)

    def test_message_falls_back_without_a_resolvable_plugin(self):
        self.env["CLAUDE_PLUGIN_ROOT"] = os.path.join(self.tmp, "missing")
        code, err = self.hook("Grep", pattern="foo")
        self.assertEqual(code, 2)
        self.assertEqual(err.strip(), "manager-plugin: map first: run the `manager-plugin:code-map`"
                         " skill's `query <term>` (or read the vault index or the map page "
                         "vault/map.md) before a broad search; if that doesn't answer it, repeat "
                         "the search and it will be allowed.")
        for env in ({}, {"CODEMAP_NUDGE_PYTHON": "python3"}, {"CODEMAP_NUDGE_ROOT": PLUGIN},
                    {"CODEMAP_NUDGE_PYTHON": "rm -rf", "CODEMAP_NUDGE_ROOT": PLUGIN},
                    {"CODEMAP_NUDGE_PYTHON": "python3", "CODEMAP_NUDGE_ROOT": "relative"}):
            with mock.patch.dict(os.environ, env):
                for k in ("CODEMAP_NUDGE_PYTHON", "CODEMAP_NUDGE_ROOT"):
                    if k not in env:
                        os.environ.pop(k, None)
                self.assertIsNone(search_nudge.map_command(), env)
        with mock.patch.dict(os.environ, {"CODEMAP_NUDGE_PYTHON": "py -3",
                                          "CODEMAP_NUDGE_ROOT": PLUGIN}):
            self.assertTrue(search_nudge.map_command().startswith('py -3 "'))

    def test_quote_path(self):
        q = search_nudge.quote_path
        self.assertEqual(q("/a b/c.py"), '"/a b/c.py"')
        self.assertEqual(q('/a"$`\\b'), '"/a\\"\\$\\`\\\\b"')
        self.assertEqual(q(r"C:\Program Files\x\codemap.py", windows=True),
                         '"C:/Program Files/x/codemap.py"')
        self.assertIsNone(q("/a\nb"))

    def new_session(self, name):
        self.session = name

    def test_non_search_commands_pass(self):
        for cmd in ("ls -la", "git status", "git log --grep foo", "python3 -m unittest",
                    "cat README.md | grep foo", "git log | rg fix", "find_tool .",
                    "echo agrep", "grep foo README.md", "grep -n foo src/app.py"):
            self.assertEqual(self.bash(cmd), 0, cmd)
        self.assertEqual(self.hook("Read", file_path="README.md")[0], 0)
        self.assertEqual(self.bash("rg foo ."), 2, "nothing above marked the session")

    def test_without_codemap_json_it_passes(self):
        os.remove(os.path.join(self.root, ".codemap.json"))
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertEqual(self.bash("grep -rn foo ."), 0)
        self.write(".codemap.json", '{"vault": "vault"}\n')
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "no map")
        os.remove(os.path.join(self.root, ".codemap.json"))
        os.symlink(os.path.join(self.root, "README.md"), os.path.join(self.root, ".codemap.json"))
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "a symlink")

    def test_outside_a_repository_it_passes(self):
        os.makedirs(os.path.join(self.tmp, "plain"))
        self.assertEqual(self.hook("Grep", pattern="foo", cwd=os.path.join(self.tmp, "plain"))[0],
                         0)

    def test_opt_out_passes(self):
        self.write(".codemap.json", '{"vault": "vault", "map": "vault/map.md", '
                   '"search_nudge": false}\n')
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertEqual(self.hook("Glob", pattern="**/*.py")[0], 0)

    def test_first_broad_grep_blocked_then_allowed(self):
        self.assert_first_blocked("Grep", pattern="foo")

    def test_first_broad_glob_blocked(self):
        self.assert_first_blocked("Glob", pattern="**/*.py")
        self.new_session("s2")
        self.assert_first_blocked("Glob", pattern="src/**/*.py")
        self.new_session("s3")
        self.assert_first_blocked("Glob", pattern="**/*.py", path=self.root)

    def test_first_broad_shell_searches_blocked(self):
        cmds = ["rg foo", "rg -n 'foo bar' .", "grep -rn foo .", "grep -R foo src",
                "find . -name '*.py'", "find src -type f", "git grep foo", "ag foo",
                "ack foo", "cd %s && grep -rn foo ." % self.root, "egrep -r 'a|b'",
                "rg --files", "/usr/bin/grep -r foo", "LC_ALL=C grep -r x .",
                "echo start; rg foo | head", "x=$(rg -l foo)", "grep -r foo * 2>/dev/null",
                "grep -r --include='*.py' foo .", "ls -la\nrg foo", "ls;\tfind ."]
        for k, cmd in enumerate(cmds):
            self.new_session("shell-%d" % k)
            self.assertEqual(self.bash(cmd), 2, cmd)
            self.assertEqual(self.bash(cmd), 0, cmd + " (repeat)")

    def test_a_broad_search_from_a_top_level_folder(self):
        self.assertEqual(self.bash("rg foo", cwd=os.path.join(self.root, "src")), 2)

    def test_narrow_searches_allowed(self):
        narrow = [("Grep", {"pattern": "foo", "path": "src/pkg"}),
                  ("Grep", {"pattern": "foo", "path": os.path.join(self.root, "src", "app.py")}),
                  ("Grep", {"pattern": "foo", "path": "README.md"}),
                  ("Grep", {"pattern": "foo", "path": "vault"}),
                  ("Grep", {"pattern": "foo", "path": "vault/map.md"}),
                  ("Grep", {"pattern": "foo", "path": "/etc"}),
                  ("Grep", {"pattern": "foo", "path": "$HOME"}),
                  ("Glob", {"pattern": "*.md"}),
                  ("Glob", {"pattern": "src/pkg/**/*.py"}),
                  ("Glob", {"pattern": "vault/**/*.md"}),
                  ("Glob", {"pattern": "**/*.py", "path": "src/pkg"}),
                  ("Glob", {"pattern": "src/app.py"}),
                  ("Bash", {"command": "rg -F handle_request src/pkg/mod.py"}),
                  ("Bash", {"command": "grep -rn foo src/pkg"}),
                  ("Bash", {"command": "find src/pkg -name '*.py'"}),
                  ("Bash", {"command": "find . -maxdepth 1 -type d"}),
                  ("Bash", {"command": "rg foo vault/"}),
                  ("Bash", {"command": "grep -r foo *.py"}),
                  ("Bash", {"command": "git -C /elsewhere grep foo"}),
                  ("Bash", {"command": "cd $DIR && rg foo"}),
                  ("Bash", {"command": "rg --version"}),
                  ("Bash", {"command": "cd src/pkg && rg foo"})]
        for tool, ti in narrow:
            self.assertEqual(self.hook(tool, **ti)[0], 0, (tool, ti))
        self.assertEqual(self.bash("rg foo", cwd=os.path.join(self.root, "src", "pkg")), 0)
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2, "narrow ones didn't count")

    def test_map_query_first_prevents_the_block(self):
        script = os.path.join(SCRIPTS, "codemap.py")
        for k, cmd in enumerate(('python3 "%s" query handler' % script,
                                 'py -3 "C:\\p\\scripts\\codemap.py" mentions --base abc',
                                 'cd %s && python3 codemap.py query x | head' % self.root)):
            self.new_session("map-%d" % k)
            self.assertEqual(self.bash(cmd), 0, cmd)
            self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, cmd)
        self.new_session("build")
        self.assertEqual(self.bash('python3 "%s" build' % script), 0)
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2, "build isn't a lookup")

    def test_sessions_and_agents_are_independent(self):
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2)
        self.new_session("other")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2)
        base = {"session_id": "other", "transcript_path": "/t/other.jsonl", "cwd": self.root,
                "tool_name": "Grep", "tool_input": {"pattern": "foo"}}
        sub = dict(base, agent_id="agent-1", agent_type="manager-plugin:worker")
        self.assertEqual(self.hook("Grep", raw=json.dumps(sub))[0], 2, "a subagent's own nudge")
        self.assertEqual(self.hook("Grep", raw=json.dumps(sub))[0], 0)
        self.assertEqual(self.hook("Grep", raw=json.dumps(base))[0], 0)
        no_session = dict(base, session_id=None)
        self.assertEqual(self.hook("Grep", raw=json.dumps(no_session))[0], 0)

    def test_corrupt_or_unwritable_state_fails_open(self):
        folder = os.path.join(self.state, search_nudge.STATE_DIR
                              + ("-%d" % os.getuid() if hasattr(os, "getuid") else ""))
        with open(folder, "w") as fh:
            fh.write("not a folder")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "state folder is a file")
        os.remove(folder)
        os.mkdir(folder)
        os.chmod(folder, 0o777)
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "a shared folder")
        os.chmod(folder, 0o700)
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2)
        for name in os.listdir(folder):
            with open(os.path.join(folder, name), "wb") as fh:
                fh.write(b"\xff garbage")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "garbage state = nudged")
        self.assertEqual(self.hook("Grep", raw="not json")[0], 0)
        self.assertEqual(self.hook("Grep", raw="")[0], 0)
        self.write(".codemap.json", "{broken")
        self.new_session("s10")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, "invalid .codemap.json")

    def folder(self):
        return os.path.join(self.state, search_nudge.STATE_DIR
                            + ("-%d" % os.getuid() if hasattr(os, "getuid") else ""))

    def data(self):
        return {"session_id": self.session, "cwd": self.root, "tool_name": "Grep",
                "tool_input": {"pattern": "foo"}}

    def listing(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.root)
                      for d, dirs, files in os.walk(self.root) for f in dirs + files)

    def test_temp_dir_inside_the_repository_fails_open(self):
        before = self.listing()
        for rel in ("tmpin", "src/tmpin"):
            inside = os.path.join(self.root, *rel.split("/"))
            os.mkdir(inside)
            os.chmod(inside, 0o500)  # any write attempt there fails (for non-root users)
            self.addCleanup(os.chmod, inside, 0o700)
            self.env["TMPDIR"] = self.env["TEMP"] = self.env["TMP"] = inside
            self.new_session("in-" + rel)
            self.assertEqual(self.hook("Grep", pattern="foo")[0], 0, rel)
            self.assertEqual(self.bash("rg foo ."), 0, rel)
            self.assertEqual(os.listdir(inside), [], rel)
        self.assertEqual(self.listing(), sorted(before + ["tmpin", "src/tmpin"]))

    def test_temp_dir_inside_the_process_cwd_fails_open(self):
        """The hook process runs elsewhere (e.g. after a Bash cd): its own cwd is kept out too."""
        other = os.path.join(self.tmp, "other")
        inside = os.path.join(other, "t")
        os.makedirs(inside)
        env = dict(self.env, TMPDIR=inside, TEMP=inside, TMP=inside)
        data = json.dumps({"session_id": "proc-cwd", "transcript_path": "/t/proc-cwd.jsonl",
                           "cwd": self.root, "hook_event_name": "PreToolUse",
                           "tool_name": "Grep", "tool_input": {"pattern": "x"}})
        p = subprocess.run(["sh", HOOK], input=data.encode(), capture_output=True, env=env,
                           cwd=other)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(os.listdir(inside), [])

    def test_temp_dir_inside_another_repository_fails_open(self):
        """E.g. a home directory that is a git repository (dotfiles) and TMPDIR=~/tmp."""
        other = os.path.join(self.tmp, "dotfiles")
        inside = os.path.join(other, "tmp")
        os.makedirs(inside)
        os.makedirs(os.path.join(other, ".git"))
        self.env["TMPDIR"] = self.env["TEMP"] = self.env["TMP"] = inside
        self.new_session("other-repo")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertEqual(os.listdir(inside), [])

    def test_state_folder_that_is_a_repository_fails_open(self):
        folder = os.path.join(self.state, search_nudge.STATE_DIR + (
            "-%d" % os.getuid() if hasattr(os, "getuid") else ""))
        os.makedirs(os.path.join(folder, ".git"))
        os.chmod(folder, 0o700)
        self.new_session("repo-state")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertEqual(sorted(os.listdir(folder)), [".git"])

    def test_no_file_is_opened_inside_the_repository(self):
        """The real lookup, spied on: no probe file, no gettempdir(), no open under the repo."""
        inside = os.path.join(self.root, "tmpin")
        os.mkdir(inside)
        opened, real_open = [], os.open

        def spy(path, *args, **kw):
            opened.append(os.path.realpath(path))
            return real_open(path, *args, **kw)
        import tempfile
        with mock.patch.dict(os.environ, {"TMPDIR": inside, "TEMP": inside, "TMP": inside}), \
                mock.patch("os.open", side_effect=spy), \
                mock.patch.object(tempfile, "gettempdir", side_effect=AssertionError):
            self.assertEqual(search_nudge.temp_base(), os.path.realpath(inside))
            self.assertEqual(search_nudge.run(self.data()), 0)
        root = os.path.realpath(self.root)
        self.assertEqual([p for p in opened if search_nudge.within(p, root)], [])
        self.assertEqual(os.listdir(inside), [])
        with mock.patch.dict(os.environ, {"TMPDIR": self.state}):
            self.assertEqual(search_nudge.run(self.data()), 2)

    def test_temp_base_skips_relative_and_missing_folders(self):
        env = {"TMPDIR": "relative", "TEMP": os.path.join(self.tmp, "missing"),
               "TMP": self.state}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(search_nudge.temp_base(), os.path.realpath(self.state))

    @unittest.skipUnless(hasattr(os, "symlink") and hasattr(os, "getuid"), "POSIX")
    def test_symlinked_state_folder_fails_open(self):
        target = os.path.join(self.tmp, "elsewhere")
        os.mkdir(target, 0o700)
        os.symlink(target, self.folder())
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertEqual(os.listdir(target), [])

    @unittest.skipUnless(hasattr(os, "getuid"), "POSIX")
    def test_state_folder_owned_by_another_user_fails_open(self):
        with mock.patch.dict(os.environ, {"TMPDIR": self.state}), \
                mock.patch.object(search_nudge.os, "getuid", return_value=os.getuid() + 1):
            self.assertEqual(search_nudge.run(self.data()), 0)
        for name in os.listdir(self.state):
            self.assertEqual(os.listdir(os.path.join(self.state, name)), [])

    @unittest.skipUnless(hasattr(os, "symlink") and hasattr(os, "getuid"), "POSIX")
    def test_planted_symlink_as_marker_fails_open(self):
        import hashlib
        os.mkdir(self.folder(), 0o700)
        key = search_nudge.state_key(dict(self.data(), transcript_path="/t/s1.jsonl"),
                                     os.path.abspath(self.root))
        marker = os.path.join(self.folder(), hashlib.sha256(key.encode()).hexdigest()[:40])
        victim = os.path.join(self.tmp, "victim")
        os.symlink(victim, marker)  # dangling: O_EXCL must not create it
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        self.assertFalse(os.path.lexists(victim))
        with open(victim, "w") as fh:
            fh.write("keep")
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 0)
        with open(victim) as fh:
            self.assertEqual(fh.read(), "keep")

    def test_state_lives_outside_the_repository(self):
        before = sorted(os.listdir(self.root))
        self.assertEqual(self.hook("Grep", pattern="foo")[0], 2)
        self.assertEqual(sorted(os.listdir(self.root)), before)
        folder = [n for n in os.listdir(self.state) if n.startswith(search_nudge.STATE_DIR)]
        self.assertEqual(len(folder), 1)
        path = os.path.join(self.state, folder[0])
        if hasattr(os, "getuid"):
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o700)
            for name in os.listdir(path):
                self.assertEqual(os.stat(os.path.join(path, name)).st_mode & 0o777, 0o600)

    def test_quoted_text_is_not_a_search(self):
        for cmd in ('echo "grep -r x ."', "echo 'rg foo'", 'git commit -m "rg foo ."',
                    "printf '%s\\n' 'find . -name x'", "echo grep -r foo .",
                    "# rg foo\nls"):
            self.assertEqual(self.bash(cmd), 0, cmd)
        self.assertEqual(self.bash('echo "x" && rg foo'), 2)

    def test_windows_style_paths_in_tool_input(self):
        self.assertEqual(self.hook("Grep", pattern="foo", path="src\\pkg")[0], 0)
        self.assertEqual(self.hook("Glob", pattern="src\\pkg\\**\\*.py")[0], 0)
        self.assertEqual(self.bash('rg foo "src\\pkg\\mod.py"'), 0)
        self.assertEqual(self.hook("Grep", pattern="foo", path="src\\")[0], 2)
        rel = search_nudge.rel_parts
        top = "C:\\Users\\me\\repo"
        self.assertEqual(rel("C:\\Users\\me\\repo", top, top), [])
        self.assertEqual(rel("c:\\users\\ME\\Repo\\src", top, top), ["src"])
        self.assertEqual(rel("src\\pkg\\mod.py", "C:/Users/me/repo", top),
                         ["src", "pkg", "mod.py"])
        self.assertEqual(rel("D:\\other", top, top), None)
        self.assertEqual(rel("..\\sibling", top, top), None)

    def test_hook_entry(self):
        with open(os.path.join(HERE, "hooks.json")) as fh:
            entries = json.load(fh)["hooks"]["PreToolUse"]
        entry = [e for e in entries if "search-nudge" in e["hooks"][0]["command"]][0]
        self.assertEqual(set(entry["matcher"].split("|")), {"Bash", "Grep", "Glob"})
        self.assertEqual(entry["hooks"][0].get("onFailure"), "continue")


class ParseTest(unittest.TestCase):
    def test_simple_commands(self):
        cmds = search_nudge.simple_commands("a 'b c' | d \"e\" 2>&1 >out && f; g # h\ni")
        self.assertEqual(cmds, [(["a", "b c"], False), (["d", "e"], True), (["f"], False),
                                (["g"], False), (["i"], False)])

    def test_search_paths(self):
        sp = search_nudge.search_paths
        self.assertEqual(sp("grep", ["-rn", "foo"], False), ["."])
        self.assertEqual(sp("grep", ["-n", "foo", "a"], False), None)
        self.assertEqual(sp("grep", ["-r", "-e", "foo", "a", "b"], False), ["a", "b"])
        self.assertEqual(sp("rg", ["-g", "*.py", "foo"], False), ["."])
        self.assertEqual(sp("rg", ["foo"], True), None)
        self.assertEqual(sp("find", ["-L", "a", "-name", "x"], False), ["a"])
        self.assertEqual(sp("git", ["--no-pager", "grep", "-n", "foo", "--", "src"], False),
                         ["src"])
        self.assertEqual(sp("git", ["log", "--grep", "x"], False), None)


if __name__ == "__main__":
    unittest.main()
