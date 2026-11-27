"""Tests for codemap.py `calls`.

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
import codemap  # noqa: E402
from test_codemap import run  # noqa: E402

FILES = {
    "pkg/__init__.py": "from pkg.core import helper\n",  # a re-export
    "pkg/core.py": (
        "import os\n"
        "\n"
        "\n"
        "def helper(x):\n"
        "    return x + 1\n"
        "\n"
        "\n"
        "def local_user():\n"
        "    return helper(2)\n"
        "\n"
        "\n"
        "class Box:\n"
        "    def size(self):\n"
        "        return 1\n"
        "\n"
        "    def double(self):\n"
        "        return self.size() * 2\n"
        "\n"
        "\n"
        "@helper\n"
        "def decorated():\n"
        "    pass\n"),
    "pkg/use_import.py": (
        "import pkg.core\n"
        "from pkg import core as c\n"
        "\n"
        "\n"
        "def one():\n"
        "    return pkg.core.helper(1)\n"
        "\n"
        "\n"
        "def two():\n"
        "    return c.helper(2)\n"),
    "pkg/use_from.py": (
        "from pkg.core import helper\n"
        "from pkg.core import helper as h\n"
        "from pkg.core import Box\n"
        "\n"
        "\n"
        "def three():\n"
        "    return helper(3) + h(4)\n"
        "\n"
        "\n"
        "def four():\n"
        "    return Box().size() + Box.size(None)\n"),
    "pkg/use_reexport.py": "from pkg import helper\n\nhelper(5)\n",
    "pkg/other.py": (
        "def uses(obj):\n"
        "    obj.helper(1)\n"
        "    fns = [helper]\n"
        "    getattr(obj, \"helper\")()\n"
        "    label = \"calls helper here\"\n"
        "    return list(map(helper, fns))\n"),
    "pkg/star.py": "from pkg.core import *\n\nhelper(6)\n",
    "pkg/broken.py": "def broken(:\n    helper(1)\n",
    "docs/notes.md": "The helper is documented here; helper twice.\n",
    "web/main.js": "helper();\n",
}

HELPER = [
    "calls helper",
    "definitions:",
    "  pkg/core.py:4 helper",
    "callers:",
    "  pkg/core.py:9 in local_user",
    "  pkg/use_from.py:7 in three",
    "  pkg/use_import.py:6 in one",
    "  pkg/use_import.py:10 in two",
    "  pkg/use_reexport.py:3 in (module level)",
    "possible:",
    "  pkg/__init__.py:1 import",
    "  pkg/core.py:20 decorator",
    "  pkg/other.py:2 attribute call",
    "  pkg/other.py:3 reference",
    "  pkg/other.py:4 getattr",
    "  pkg/other.py:6 reference",
    "  pkg/star.py:3 call",
    "  pkg/use_from.py:1 import",
    "  pkg/use_from.py:2 import",
    "  pkg/use_reexport.py:1 import",
    "  pkg/other.py:5 string",  # strings after the code entries
    # 18 in Python (1 in broken.py, not parsed), 2 in notes.md, 1 in main.js
    "text: 21 occurrences of helper, 17 on lines listed above; grep the rest",
    "not parsed: pkg/broken.py (syntax error, line 1)",
    codemap.CALLS_COVERAGE,
]


class CallsTest(unittest.TestCase):
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
                              + list(args), capture_output=True, check=True).stdout.decode()

    def calls(self, *args):
        code, out = run("calls", *args, "--root", self.root)
        self.assertEqual(code, 0)
        self.assertNotIn("no callers", out)
        self.assertEqual(out.splitlines()[-1], codemap.CALLS_COVERAGE)
        return out.splitlines()

    def refused(self, *args):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            run(*args, "--root", self.root)
        self.assertEqual(stop.exception.code, 2, args)

    def snapshot(self):
        found = {}
        for d, dirs, names in os.walk(self.root):
            dirs[:] = [x for x in dirs if x != ".git"]  # git status refreshes its index
            for name in names:
                path = os.path.join(d, name)
                found[path] = (os.path.getmtime(path), os.path.getsize(path))
        return found

    def test_the_full_answer(self):
        self.assertEqual(self.calls("helper"), HELPER)

    def test_a_qualified_name_finds_the_same_definition(self):
        for name in ("core.helper", "pkg.core.helper"):
            self.assertEqual(self.calls(name)[1:], HELPER[1:], name)
        lines = self.calls("other.helper")  # no such definition: nothing is confident
        self.assertEqual(lines[1:4], ["definitions: none found", "callers: none found",
                                      "possible:"])
        self.assertIn("  pkg/use_import.py:6 attribute call", lines)
        self.assertIn("  pkg/core.py:4 other definition", lines)

    def test_methods(self):
        lines = self.calls("Box.size")
        self.assertEqual(lines[:6], [
            "calls Box.size", "definitions:", "  pkg/core.py:13 Box.size", "callers:",
            "  pkg/core.py:17 in Box.double", "  pkg/use_from.py:11 in four"])
        self.assertEqual(lines[6:8], ["possible:", "  pkg/use_from.py:11 attribute call"])

    def test_nothing_found_still_ends_with_coverage(self):
        self.assertEqual(self.calls("nowhere"), [
            "calls nowhere", "definitions: none found", "callers: none found",
            "possible: none found", "text: 0 occurrences of nowhere, all on lines listed above",
            "not parsed: pkg/broken.py (syntax error, line 1)", codemap.CALLS_COVERAGE])
        self.write("pkg/broken.py", "")
        self.assertEqual(self.calls("nowhere")[-2:],
                         ["text: 0 occurrences of nowhere, all on lines listed above",
                          codemap.CALLS_COVERAGE])

    def test_several_names_one_coverage_line(self):
        lines = self.calls("Box.size", "helper")
        self.assertEqual(lines.count(codemap.CALLS_COVERAGE), 1)
        self.assertEqual([x for x in lines if x.startswith("calls ")],
                         ["calls Box.size", "calls helper"])
        self.assertEqual(lines[lines.index("calls helper"):], HELPER)

    def test_deterministic_and_writes_nothing(self):
        before, status = self.snapshot(), self.git("status", "--porcelain")
        self.assertEqual(self.calls("helper"), self.calls("helper"))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_map_pages_and_sensitive_files_are_not_counted(self):
        self.assertEqual(run("build", "--root", self.root)[0], 0)
        self.write("secrets/keys.py", "helper = 1\n")
        self.git("add", "-A")
        self.assertEqual(self.calls("helper"), HELPER)

    def test_the_cap_and_all(self):
        self.write("pkg/many.py", "from pkg.core import helper\n"
                   + "".join("helper(%d)\n" % n for n in range(45)))
        self.git("add", "-A")
        lines = self.calls("helper")
        callers = lines[lines.index("callers:") + 1:lines.index("possible:")]
        self.assertEqual(len(callers), codemap.CALLS_LIMIT + 1)
        self.assertEqual(callers[-1], "  … 10 more (rerun with --all)")  # 5 + 45 callers
        self.assertEqual(lines[-3], "text: 67 occurrences of helper, 53 on lines listed above; "
                                    "grep the rest")
        full = self.calls("helper", "--all")
        callers = full[full.index("callers:") + 1:full.index("possible:")]
        self.assertEqual(len(callers), 50)
        self.assertFalse(any("rerun with --all" in x for x in full))
        self.assertIn("63 on lines listed above", full[-3])

    def test_unreadable_python_is_named(self):
        with open(os.path.join(self.root, "pkg", "blob.py"), "wb") as fh:
            fh.write(b"\0helper\n")
        self.git("add", "-A")
        self.assertEqual(self.calls("x")[-2], "not parsed: pkg/blob.py (unreadable, too large or "
                                              "not text), pkg/broken.py (syntax error, line 1)")

    def test_alias_of_an_unresolved_import_stays_possible(self):
        self.write("pkg/alias.py", "from elsewhere import helper as hp\n\nhp(1)\nx = hp\n")
        self.git("add", "-A")
        lines = self.calls("helper")
        for line in ("  pkg/alias.py:1 import", "  pkg/alias.py:3 call (alias hp)",
                     "  pkg/alias.py:4 reference (alias hp)"):
            self.assertIn(line, lines)

    def test_assignment_and_attribute_reference(self):
        self.write("pkg/patch.py", "import pkg.core\n\npkg.core.helper = print\nf = pkg.core.helper"
                                   "\nhelper = 3\n")
        self.git("add", "-A")
        lines = self.calls("helper")
        for line in ("  pkg/patch.py:3 assignment", "  pkg/patch.py:4 attribute reference",
                     "  pkg/patch.py:5 assignment"):
            self.assertIn(line, lines)

    def test_refusals(self):
        self.refused("calls")
        self.refused("calls", "not a name")
        self.refused("calls", "helper(")
        self.refused("query", "helper", "--all")
        self.refused("calls", "helper", "--budget", "9")


if __name__ == "__main__":
    unittest.main()
