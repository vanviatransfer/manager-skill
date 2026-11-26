"""Tests for codemap.py `impact` and `query --budget`.

python3 -m unittest discover -s <this folder>
"""
import contextlib
import io
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import portability  # noqa: E402  (in the plugin folder)
from test_codemap import run  # noqa: E402

# A chain a -> b -> c (a imports b, b imports c), another importer of c, a test of c, a file whose
# name only contains "core", and a vault.
FILES = {
    "pkg/c.py": "def core():\n    return 1\n\n\nclass Store:\n    pass\n",
    "pkg/b.py": "from pkg import c\n\n\ndef middle():\n    return c.core()\n",
    "pkg/a.py": "from pkg import b\n\n\ndef top():\n    return b.middle()\n",
    "pkg/core_utils.py": "def core_helper():\n    return 2\n",
    "pkg/score.py": "from pkg import c\n\n\ndef score():\n    return c.Store()\n",
    "tests/test_c.py": "from pkg.c import core\n\n\ndef test_core():\n    assert core() == 1\n",
    "docs/vault/index.md": "# Index\n\nThe core lives in `pkg/c.py`.\n",
    "docs/vault/core.md": "# Core notes\n\nSee [[index]].\n",
}

# `query` output at plugin 0.9.10, before `--budget` existed: without it, nothing may change.
GOLDEN = {
    "core": """defined:
  pkg/c.py:1 core
  pkg/core_utils.py:1 core_helper
  pkg/score.py:4 score
  tests/test_c.py:4 test_core
paths:
  pkg/core_utils.py (imported by 0 local files)
  pkg/score.py (imported by 0 local files)
vault pages:
  docs/vault/core.md — Core notes (5 words, linked from 0)
""",
    "c.py": """defined: none
paths:
  pkg/c.py (imported by 3 local files)
    <- pkg/b.py
    <- pkg/score.py
    <- tests/test_c.py
    mentioned in docs/vault/index.md:3
  tests/test_c.py (imported by 0 local files)
vault pages: none
""",
    "zzz": "defined: none\npaths: none\nvault pages: none\n",
}


class ImpactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        for rel, text in FILES.items():
            self.write(rel, text)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.git("add", "-A")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t"]
                              + list(args), capture_output=True, check=True).stdout.decode().strip()

    def refused(self, *args):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            run(*args, "--root", self.root)
        self.assertEqual(stop.exception.code, 2, args)

    def impact(self, *args):
        code, out = run("impact", *args, "--root", self.root)
        self.assertEqual(code, 0)
        return out.splitlines()

    def test_impact_lists_the_chain_and_the_test(self):
        lines = self.impact("pkg/c.py")
        self.assertIn("import-based", lines[0])
        self.assertIn("name-based, may include false matches", lines[0])
        self.assertEqual(lines[1:], [
            "pkg/c.py",
            "  imported by: pkg/b.py, pkg/score.py",
            "  depth 2: pkg/a.py",
            "  tests: tests/test_c.py",
            "  referenced: core: pkg/b.py, tests/test_c.py",
            "  referenced: Store: pkg/score.py",
        ])

    def test_depth_limits_the_dependents(self):
        lines = self.impact("pkg/c.py", "--depth", "1")
        self.assertIn("  imported by: pkg/b.py, pkg/score.py", lines)
        self.assertFalse(any("pkg/a.py" in line for line in lines), lines)
        self.refused("impact", "pkg/c.py", "--depth", "0")

    def test_each_dependent_once_and_other_files_named(self):
        self.write("pkg/a.py", "from pkg import b, c\n\n\ndef top():\n    return b.middle()\n")
        self.git("add", "-A")
        lines = self.impact("./pkg/c.py", "README.md")
        self.assertIn("  imported by: pkg/a.py, pkg/b.py, pkg/score.py", lines)
        self.assertFalse(any(line.startswith("  depth") for line in lines), lines)
        self.assertEqual(lines[-1], "not a source file in the map (other type, skipped or "
                                    "deleted): README.md")

    def test_base_takes_the_changed_files(self):
        self.git("commit", "-q", "-m", "fixture")
        base = self.git("rev-parse", "HEAD")
        self.write("pkg/c.py", FILES["pkg/c.py"] + "\n\ndef extra():\n    pass\n")
        lines = self.impact("--base", base)
        self.assertTrue(lines[0].startswith("impact: 1 source file "), lines[0])
        self.assertEqual(lines[1:4], ["pkg/c.py", "  imported by: pkg/b.py, pkg/score.py",
                                      "  depth 2: pkg/a.py"])
        self.refused("impact")  # no paths, no --base

    def test_query_without_budget_is_unchanged(self):
        for term, expected in GOLDEN.items():
            code, out = run("query", term, "--root", self.root)
            self.assertEqual((code, out), (0, expected), term)

    def test_budget_cut_keeps_the_exact_match(self):
        code, out = run("query", "core", "--budget", "1", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertEqual(out, "defined:\n  pkg/c.py:1 core\n… 6 more (raise --budget)\n")
        out = run("query", "core", "--budget", "40", "--root", self.root)[1]
        self.assertLessEqual(len(out), 40 * 4)
        self.assertIn("docs/vault/core.md", out)  # an exact page name ranks next
        self.assertTrue(out.endswith(" more (raise --budget)\n"), out)

    def test_budget_ranks_by_importers_and_ends_without_a_cut(self):
        out = run("query", "py", "--budget", "1000", "--root", self.root)[1]
        lines = out.splitlines()
        self.assertEqual(lines[lines.index("paths:") + 1], "  pkg/c.py (imported by 3 local files)")
        self.assertNotIn("raise --budget", out)
        self.assertEqual(run("query", "zzz", "--budget", "5", "--root", self.root)[1],
                         GOLDEN["zzz"])
        for bad in (["query", "core", "--budget", "0"], ["impact", "pkg/c.py", "--budget", "9"]):
            self.refused(*bad)


if __name__ == "__main__":
    unittest.main()
