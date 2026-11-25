"""The scan guard against its adversarial corpus (scan_guard_corpus.json): every entry through
scan_guard.refused and through the real sh hook; per category, the leaks (a root scan that
passes) and the false blocks (normal work refused), for each. Any mismatch fails, except an
entry marked `known_gap` (the predicate's) or `hook_gap` (the sh hook's only), which is reported;
a marked entry that no longer mismatches fails too, so its mark is dropped:
python3 -m unittest discover -s <this folder>"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from collections import Counter
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "scan_guard_corpus.json")
GUARD = os.path.join(HERE, "scan-guard.sh")
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
sys.path.insert(0, os.path.join(PLUGIN, "skills", "code-map", "scripts"))
import scan_guard  # noqa: E402

TOOLS = {"Bash", "PowerShell", "Glob", "Grep"}
FIELDS = {"cat", "tool", "input", "cwd", "env", "dirs", "expect", "note", "known_gap", "hook_gap"}
REAL_ISDIR = os.path.isdir


def load():
    with open(CORPUS, encoding="utf-8") as fh:
        return json.load(fh)


CORPUS_DATA = load()


def hook_input(entry):
    cwd = entry.get("cwd") or CORPUS_DATA["cwd"][entry["tool"]]
    return {"session_id": "corpus", "cwd": cwd, "hook_event_name": "PreToolUse",
            "tool_name": entry["tool"], "tool_input": entry["input"]}


def label(entry):
    return "%s %s %s" % (entry["cat"], entry["tool"], json.dumps(entry["input"]))


def predicate(entry):
    """True if scan_guard.refused refuses the entry; its `dirs` count as existing folders, its
    `env` is set."""
    dirs = set(entry.get("dirs", ()))
    with mock.patch("os.path.isdir", lambda p: p in dirs or REAL_ISDIR(p)), \
            mock.patch.dict(os.environ, entry.get("env", {})):
        return scan_guard.refused(hook_input(entry)) is not None


def tally(entries, results, gap_key):
    """({category: Counter(entries, leaks, false blocks, gaps)}, mismatches, reported gaps);
    gap_key(entry) is the entry's gap reason at this level, or None."""
    table, bad, gaps = {}, [], []
    for entry, blocked in zip(entries, results):
        row = table.setdefault(entry["cat"], Counter())
        row["entries"] += 1
        want = entry["expect"] == "block"
        gap = gap_key(entry)
        if blocked == want:
            if gap:
                bad.append("gap mark no longer mismatches, drop it: " + label(entry))
            continue
        kind = "leak" if want else "false block"
        if gap:
            row["gap"] += 1
            gaps.append("%s (%s): %s" % (kind, gap, label(entry)))
        else:
            row[kind] += 1
            bad.append("%s: %s" % (kind, label(entry)))
    return table, bad, gaps


def report(title, table, gaps):
    lines = ["", "scan guard corpus, %s: category, entries, leaks, false blocks, known gaps"
             % title]
    total = Counter()
    for cat in sorted(table) + ["total"]:
        row = total if cat == "total" else table[cat]
        if cat != "total":
            total.update(row)
        lines.append("  %-14s %4d %4d %4d %4d" % (cat, row["entries"], row["leak"],
                                                 row["false block"], row["gap"]))
    lines += ["  known gap, " + g for g in gaps]
    sys.stderr.write("\n".join(lines) + "\n")


class CorpusTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"HOME": CORPUS_DATA["home"]})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("USERPROFILE", None)
        self.entries = CORPUS_DATA["entries"]

    def run_hook(self, data, env):
        p = subprocess.run(["sh", GUARD], input=json.dumps(data).encode(), capture_output=True,
                           env=env)
        return p.returncode

    def hook_env(self, home):
        tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, tmp)
        env = dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp, PYTHONDONTWRITEBYTECODE="1",
                   HOME=home, CLAUDE_PLUGIN_ROOT=PLUGIN)
        env.pop("USERPROFILE", None)
        return env

    def test_entries_are_well_formed(self):
        self.assertGreaterEqual(len(self.entries), 150)
        seen = set()
        for e in self.entries:
            self.assertLessEqual(set(e), FIELDS, e)
            self.assertIn(e["tool"], TOOLS, e)
            self.assertIn(e["expect"], ("block", "pass"), e)
            self.assertIsInstance(e["input"], dict, e)
            self.assertTrue(e["note"] and e["cat"], e)
            self.assertFalse(e.get("known_gap") and e.get("hook_gap"), e)
            key = (e["tool"], json.dumps(e["input"], sort_keys=True), e.get("cwd"),
                   json.dumps(e.get("env"), sort_keys=True), json.dumps(e.get("dirs")))
            self.assertNotIn(key, seen, "duplicate entry: %s" % label(e))
            seen.add(key)
        expects = Counter(e["expect"] for e in self.entries)
        self.assertGreater(expects["pass"], 0)
        self.assertGreater(expects["block"], 0)

    def test_corpus_through_the_predicate(self):
        results = [predicate(e) for e in self.entries]
        table, bad, gaps = tally(self.entries, results, lambda e: e.get("known_gap"))
        report("predicate", table, gaps)
        self.assertEqual(bad, [], "\n".join(bad))

    def test_corpus_through_the_sh_hook(self):
        """The real wrapper (its grep pre-filter, its Python lookup). Run for every entry that
        is to be refused or that the predicate refuses; for the rest the hook exits 0 whatever
        the pre-filter does. Entries with `dirs` need a mocked folder: the predicate's result."""
        env = self.hook_env(CORPUS_DATA["home"])
        results, bad = [], []
        for e in self.entries:
            pred = predicate(e)
            if e.get("dirs") or not (pred or e["expect"] == "block"):
                results.append(pred)
                continue
            blocked = self.run_hook(hook_input(e), dict(env, **e.get("env", {}))) == 2
            results.append(blocked)
            if blocked != pred and not e.get("hook_gap"):
                bad.append("hook and predicate differ: " + label(e))
        table, mismatches, gaps = tally(self.entries, results,
                                        lambda e: e.get("known_gap") or e.get("hook_gap"))
        report("sh hook", table, gaps)
        self.assertEqual(bad + mismatches, [], "\n".join(bad + mismatches))

    def test_dotted_folder_under_a_root_is_a_folder(self):
        """cmd `dir /s <root>\\<a.b>`: an existing folder is scanned alone, a file name is
        searched for over the whole root."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, tmp)
        home = os.path.join(tmp, "home")
        os.makedirs(os.path.join(home, "my.app"))
        os.makedirs(os.path.join(home, "site.github.io"))
        env = self.hook_env(home)
        with mock.patch.dict(os.environ, {"HOME": home}):
            for name, want in (("my.app", 0), ("site.github.io", 0), ("codemap.py", 2),
                               ("*.py", 2)):
                # Relative to the home cwd (cmd takes a `/tmp/...` word for a switch).
                cmd = "cmd /c dir /s .\\%s" % name
                data = {"session_id": "d", "cwd": home, "hook_event_name": "PreToolUse",
                        "tool_name": "PowerShell", "tool_input": {"command": cmd}}
                self.assertEqual(scan_guard.refused(data) is not None, want == 2, cmd)
                self.assertEqual(self.run_hook(data, env), want, cmd)

    def test_many_here_documents_in_time(self):
        """Here-document detection is one pass per line and looks at MAX_HEREDOCS openers."""
        for cmd in ("cat " + "<<A " * (63 * 1024 // 4), "echo '" + "sh <<B " * 9000 + "'"):
            self.assertLessEqual(len(cmd), scan_guard.MAX_COMMAND)
            start = time.monotonic()
            self.assertIsNone(scan_guard.refused({"cwd": "/home/tester/proj", "tool_name": "Bash",
                                                  "tool_input": {"command": cmd}}))
            self.assertLess(time.monotonic() - start, 1.0, cmd[:20])

    def test_long_command_fails_open_in_time(self):
        script = base64.b64encode(("Write-Host x;" * 40000).encode("utf-16-le")).decode()
        cmd = "find / -name x; powershell -e " + script
        self.assertGreater(len(cmd), scan_guard.MAX_COMMAND)
        start = time.monotonic()
        for tool in ("Bash", "PowerShell"):
            data = {"cwd": CORPUS_DATA["cwd"][tool], "tool_name": tool,
                    "tool_input": {"command": cmd}}
            self.assertIsNone(scan_guard.refused(data), "over the cap: not scanned")
        self.assertLess(time.monotonic() - start, 1.0)
        short = "find / -name x; powershell -e " + script[:1000]
        self.assertLessEqual(len(short), scan_guard.MAX_COMMAND)
        self.assertIsNotNone(scan_guard.refused({"cwd": "/home/tester/proj", "tool_name": "Bash",
                                                 "tool_input": {"command": short}}))


if __name__ == "__main__":
    unittest.main()
