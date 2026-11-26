"""Tests for the `possible weakened guards` section of codemap.py `changed`.

python3 -m unittest discover -s <this folder>
"""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import portability  # noqa: E402  (in the plugin folder)
import codemap  # noqa: E402
from test_codemap import GIT_ENV, run  # noqa: E402

HEADER = "possible weakened guards (approximate, never a filter):"
# Marker text is built from pieces so this file's own diff doesn't plant what it tests.
SKIP = "@unittest." + "skip"
NOQA = "# no" + "qa"

BASE = {
    "app/core.py": "def run():\n    return 1\n",
    "tests/test_core.py": ("import unittest\nfrom app.core import run\n\n\n"
                           "class T(unittest.TestCase):\n    def test_run(self):\n"
                           "        self.assertEqual(run(), 1)\n        self.assertTrue(run())\n"
                           "        assert run() == 1\n"),
    "tests/test_gone.py": "def test_gone():\n    assert True\n",
    "tests/test_moved.py": "def test_moved():\n    assert 1 == 1\n    assert 2 == 2\n",
    "web/app.test.js": "it('works', () => {\n  expect(1).toBe(1);\n});\n",
    "pyproject.toml": "[project]\nname = \"x\"\n\n[tool.ruff]\nline-length = 100\n",
    ".github/workflows/ci.yml": "on: push\njobs: {}\n",
    "README.md": "readme\n",
}


class WeakenedGuardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = portability.temp_dir()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        for rel, text in BASE.items():
            self.write(rel, text)
        self.git("init", "-q")
        self.base = self.commit("base")

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def remove(self, rel):
        os.remove(os.path.join(self.root, *rel.split("/")))

    def git(self, *args):
        os.makedirs(self.root, exist_ok=True)
        p = subprocess.run(["git", "-C", self.root] + list(args), capture_output=True, env=GIT_ENV)
        if p.returncode:
            raise AssertionError("git %s: %s" % (args, p.stderr.decode()))
        return p.stdout.decode()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD").strip()

    def changed(self, base, head):
        code, out = run("changed", "--base", base, "--head", head, "--root", self.root)
        self.assertEqual(code, 0)
        return out

    def section(self, out):
        lines = out.splitlines()
        return lines[lines.index(HEADER):] if HEADER in lines else []

    def plant(self):
        """Every kind of finding once; the head commit's id."""
        self.remove("tests/test_gone.py")
        os.makedirs(os.path.join(self.root, "attic"))
        self.git("mv", "tests/test_moved.py", "attic/test_moved.py")
        self.write("tests/test_core.py", BASE["tests/test_core.py"].replace(
            "        self.assertTrue(run())\n        assert run() == 1\n", "").replace(
            "    def test_run", "    %s(\"later\")\n    def test_run" % SKIP))
        self.write("web/app.test.js", BASE["web/app.test.js"].replace("it(", "it.only("))
        self.write("pyproject.toml", BASE["pyproject.toml"].replace("100", "200"))
        self.write(".github/workflows/ci.yml", "on: push\n")
        self.write("app/core.py", "import os  %s\n\n\ndef run():\n    return 1\n" % NOQA)
        self.write("README.md", "readme: %s, %s\n" % (SKIP, NOQA))  # prose: no finding
        return self.commit("head")

    def test_planted_weakenings_are_flagged(self):
        head = self.plant()
        self.assertEqual(self.section(self.changed(self.base, head)), [
            HEADER,
            "  test file: tests/test_gone.py: deleted",
            "  test file: tests/test_moved.py: moved to attic/test_moved.py",
            "  skip marker: tests/test_core.py: +1 @unittest.skip",
            "  skip marker: web/app.test.js: +1 .only(",
            "  asserts: tests/test_core.py: 2 fewer assert/expect lines",
            "  check config: .github/workflows/ci.yml: CI config edited",
            "  check config: pyproject.toml: [tool.ruff] edited",
            "  suppression: app/core.py: +1 noqa",
        ])

    def test_at_most_eight_lines_then_a_count(self):
        self.assertEqual(codemap.MAX_GUARD_LINES, 8)
        self.plant()
        for n in range(3):
            self.write("lint%d/.flake8" % n, "[flake8]\n")
        head = self.commit("more")
        section = self.section(self.changed(self.base, head))
        self.assertEqual(len(section), 1 + 8 + 1)
        self.assertEqual(section[-1], "  … 3 more")

    def test_rename_kinds_and_a_test_no_longer_named_as_one(self):
        self.git("mv", "tests/test_moved.py", "tests/test_other.py")
        os.makedirs(os.path.join(self.root, "attic"))
        self.git("mv", "tests/test_gone.py", "attic/gone.py")
        head = self.commit("renames")
        self.assertEqual(self.section(self.changed(self.base, head)), [
            HEADER,
            "  test file: tests/test_gone.py: moved and renamed to attic/gone.py, no longer "
            "named as a test",
            "  test file: tests/test_moved.py: renamed to tests/test_other.py"])

    def test_moved_lines_and_other_files_count_for_nothing(self):
        # the same asserts in another order; a skip word in a non-test file; a tool-less
        # pyproject edit; a generic `.skip(` outside a test file
        self.write("tests/test_core.py", BASE["tests/test_core.py"].replace(
            "        self.assertTrue(run())\n        assert run() == 1\n",
            "        assert run() == 1\n        self.assertTrue(run())\n"))
        self.write("pyproject.toml", BASE["pyproject.toml"].replace("\"x\"", "\"y\""))
        self.write("app/core.py", "def run():\n    return [1, 2].skip(1)\n")
        head = self.commit("harmless")
        out = self.changed(self.base, head)
        self.assertNotIn(HEADER, out)

    def test_without_findings_the_output_is_unchanged(self):
        """Golden: the `changed` output of 0.9.12 for a diff with nothing to flag."""
        self.write("app/core.py", "def run():\n    return 2\n")
        head = self.commit("edit")
        self.assertEqual(self.changed(self.base, head),
                         "changed: 1 file\nM app/core.py\n  definitions: run\n"
                         "  tests: tests/test_core.py\n")
        self.assertEqual(self.changed(head, head), "changed: 0 files\n")


class MarkerUnitTest(unittest.TestCase):
    def test_marks(self):
        skips, quiet, asserts = codemap.guard_marks(
            "@pytest.mark.skip\npytest.mark.xfail\nx.skip(1)  # type: ignore\n"
            "t.Skip(\"no\")\n@Disabled\nself.skipTest('x')\nxit('a')\nxdescribe('b')\n"
            "// eslint-disable-next-line\n// @ts-ignore\nx := 1 //nolint\n"
            "if x:  # pragma: no cover\nexpect(a)\nassertThat(b)\n", True)
        self.assertEqual(skips, {"pytest.mark.skip": 1, "pytest.mark.xfail": 1, ".skip(": 1,
                                 "t.Skip(": 1, "@Disabled": 1, "skipTest(": 1, "xit(": 1,
                                 "xdescribe(": 1})
        self.assertEqual(quiet, {"type: ignore": 1, "eslint-disable": 1, "@ts-ignore": 1,
                                 "nolint": 1, "pragma: no cover": 1})
        self.assertEqual(asserts, 2)
        self.assertEqual(codemap.guard_marks("x.only(1)\nexpect(a)\n", False), ({}, {}, 0))

    def test_check_config(self):
        for path, kind in ((".github/workflows/ci.yml", "CI"), (".gitlab-ci.yml", "CI"),
                           (".pre-commit-config.yaml", "pre-commit"), ("setup.cfg", "lint/test"),
                           ("tox.ini", "lint/test"), ("web/.eslintrc.json", "lint"),
                           (".flake8", "lint"), ("mypy.ini", "type-check"),
                           ("tsconfig.build.json", "type-check"), ("ruff.toml", "lint"),
                           (".golangci.yml", "lint"), (".prettierrc", "format"),
                           ("pyproject.toml", None), ("src/workflows/ci.yml", None),
                           ("README.md", None)):
            self.assertEqual(codemap.check_config(path), kind, path)


if __name__ == "__main__":
    unittest.main()
