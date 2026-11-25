"""The scan guard against its adversarial corpus (scan_guard_corpus.json): every entry through
scan_guard.refused, a sample through the real sh hook; per category, the leaks (a root scan that
passes) and the false blocks (normal work refused). Any mismatch fails, except an entry marked
`known_gap`, which is reported (and fails once it no longer mismatches, so the mark is dropped):
python3 -m unittest discover -s <this folder>"""
import json
import os
import subprocess
import sys
import tempfile
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
FIELDS = {"cat", "tool", "input", "cwd", "expect", "note", "known_gap"}
SAMPLE_EVERY = 5  # every 5th entry, and every one the sh pre-filter must let through, run in sh


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


def tally(entries, results):
    """{category: Counter(entries, leaks, false blocks, gaps)} and the mismatches."""
    table, bad, gaps = {}, [], []
    for entry, blocked in zip(entries, results):
        row = table.setdefault(entry["cat"], Counter())
        row["entries"] += 1
        want = entry["expect"] == "block"
        if blocked == want:
            if entry.get("known_gap"):
                bad.append("known_gap no longer mismatches, drop the mark: " + label(entry))
            continue
        kind = "leak" if want else "false block"
        if entry.get("known_gap"):
            row["gap " + kind] += 1
            gaps.append("%s (%s): %s" % (kind, entry["known_gap"], label(entry)))
        else:
            row[kind] += 1
            bad.append("%s: %s" % (kind, label(entry)))
    return table, bad, gaps


def report(table, gaps):
    lines = ["", "scan guard corpus: category, entries, leaks, false blocks, known gaps"]
    total = Counter()
    for cat in sorted(table):
        row = table[cat]
        total.update(row)
        lines.append("  %-14s %4d %4d %4d %4d" % (cat, row["entries"], row["leak"],
                                                 row["false block"],
                                                 row["gap leak"] + row["gap false block"]))
    lines.append("  %-14s %4d %4d %4d %4d" % ("total", total["entries"], total["leak"],
                                             total["false block"],
                                             total["gap leak"] + total["gap false block"]))
    lines += ["  known gap, " + g for g in gaps]
    sys.stderr.write("\n".join(lines) + "\n")


class CorpusTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"HOME": CORPUS_DATA["home"]})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("USERPROFILE", None)
        self.entries = CORPUS_DATA["entries"]

    def test_entries_are_well_formed(self):
        self.assertGreaterEqual(len(self.entries), 150)
        seen = set()
        for e in self.entries:
            self.assertLessEqual(set(e), FIELDS, e)
            self.assertIn(e["tool"], TOOLS, e)
            self.assertIn(e["expect"], ("block", "pass"), e)
            self.assertIsInstance(e["input"], dict, e)
            self.assertTrue(e["note"] and e["cat"], e)
            key = (e["tool"], json.dumps(e["input"], sort_keys=True), e.get("cwd"))
            self.assertNotIn(key, seen, "duplicate entry: %s" % label(e))
            seen.add(key)
        expects = Counter(e["expect"] for e in self.entries)
        self.assertGreater(expects["pass"], 0)
        self.assertGreater(expects["block"], 0)

    def test_corpus_through_the_predicate(self):
        results = [scan_guard.refused(hook_input(e)) is not None for e in self.entries]
        table, bad, gaps = tally(self.entries, results)
        report(table, gaps)
        self.assertEqual(bad, [], "\n".join(bad))

    def test_sample_through_the_sh_hook(self):
        """The real wrapper (its grep pre-filter, its Python lookup) agrees with the predicate."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, tmp)
        env = dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp, PYTHONDONTWRITEBYTECODE="1",
                   HOME=CORPUS_DATA["home"], CLAUDE_PLUGIN_ROOT=PLUGIN)
        env.pop("USERPROFILE", None)
        sample = [e for k, e in enumerate(self.entries) if k % SAMPLE_EVERY == 0 or
                  e["cat"] == "incident" or
                  any(w in e["input"].get("command", "") for w in ("-enc", "-Enc", "-e ",
                                                                    "forfiles"))]
        self.assertGreater(len(sample), len(self.entries) // SAMPLE_EVERY)
        for e in sample:
            data = hook_input(e)
            p = subprocess.run(["sh", GUARD], input=json.dumps(data).encode(),
                               capture_output=True, env=env)
            want = 2 if scan_guard.refused(data) else 0
            self.assertEqual(p.returncode, want, (label(e), p.stderr.decode()[:200]))


if __name__ == "__main__":
    unittest.main()
