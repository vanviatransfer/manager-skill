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
    "  pkg/use_from.py:2 import (alias h)",
    "  pkg/use_reexport.py:1 import",
    "  pkg/other.py:5 string",  # strings after the code entries
    # 18 in Python (1 in broken.py, not parsed), 2 in notes.md, 1 in main.js
    "text: 21 occurrences of helper, 17 on lines listed above; renamed: h; passed or stored at 2 "
    "places, calls through them not followed; 12 possible; 1 Python file not parsed; grep the "
    "rest",
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
            "possible: none found", "text: 0 occurrences of nowhere, 0 on lines listed above; "
            "1 Python file not parsed; grep the rest",
            "not parsed: pkg/broken.py (syntax error, line 1)", codemap.CALLS_COVERAGE])
        self.write("pkg/broken.py", "")
        self.assertEqual(self.calls("nowhere")[-2:],
                         ["text: 0 occurrences of nowhere, all on lines listed above (tracked "
                          "files only)", codemap.CALLS_COVERAGE])

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
                                    "renamed: h; passed or stored at 2 places, calls through "
                                    "them not followed; 13 possible; 1 Python file not parsed; "
                                    "cut (rerun with --all); grep the rest")
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
                     "  pkg/alias.py:4 renamed to x"):
            self.assertIn(line, lines)

    def test_assignment_and_attribute_reference(self):
        self.write("pkg/patch.py", "import pkg.core\n\npkg.core.helper = print\nf = pkg.core.helper"
                                   "\nhelper = 3\ng = [pkg.core.helper]\n")
        self.git("add", "-A")
        lines = self.calls("helper")
        for line in ("  pkg/patch.py:3 assignment", "  pkg/patch.py:4 renamed to f",
                     "  pkg/patch.py:5 assignment", "  pkg/patch.py:6 attribute reference"):
            self.assertIn(line, lines)

    def test_a_stored_reference_is_no_complete_list(self):
        self.write("pkg/table.py", "from pkg.core import local_user\n\nFNS = [local_user]\n"
                                   "FNS[0]()\n")
        self.git("add", "-A")
        self.assertEqual(self.calls("local_user")[-3], (
            "text: 3 occurrences of local_user, 3 on lines listed above; passed or stored at 1 "
            "place, calls through it not followed; 2 possible; 1 Python file not parsed; grep "
            "the rest"))
        self.write("pkg/broken.py", "")
        self.assertEqual(self.calls("double")[-2], "text: 1 occurrence of double, all on lines "
                                                   "listed above (tracked files only)")

    def test_refusals(self):
        self.refused("calls")
        self.refused("calls", "not a name")
        self.refused("calls", "helper(")
        self.refused("query", "helper", "--all")
        self.refused("calls", "helper", "--budget", "9")


# The target bound under other names: a renamed re-export, an alias imported into a second file,
# a module-level alias imported elsewhere.
RENAMED = {
    "pkg/core.py": "def helper(x):\n    return x\n",
    "pkg/__init__.py": "from .core import helper as public_helper\n",
    "app.py": "from pkg import public_helper\n\n\ndef main():\n    public_helper(1)\n",
    "shim.py": "from pkg.core import helper as h\n",
    "user.py": "from shim import h\n\n\ndef run():\n    h(2)\n",
    "al.py": "from pkg import core\nalias = core.helper\n",
    "al_user.py": "from al import alias\nalias(3)\n",
}


class RenamedTest(CallsTest):
    def setUp(self):
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        for rel, text in RENAMED.items():
            self.write(rel, text)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.git("add", "-A")

    def test_calls_through_other_names_are_callers(self):
        for name in ("helper", "pkg.core.helper"):
            self.assertEqual(self.calls(name)[1:-1], [
                "definitions:", "  pkg/core.py:1 helper",
                "callers:", "  al_user.py:2 in (module level)", "  app.py:5 in main",
                "  user.py:5 in run",
                "possible:", "  al.py:2 assignment (alias alias)", "  al.py:2 renamed to alias",
                "  al_user.py:1 import (alias alias)", "  app.py:1 import (alias public_helper)",
                "  pkg/__init__.py:1 import", "  pkg/__init__.py:1 import (alias public_helper)",
                "  shim.py:1 import", "  shim.py:1 import (alias h)",
                "  user.py:1 import (alias h)",
                "text: 4 occurrences of helper, 4 on lines listed above; renamed: alias, h, "
                "public_helper; 9 possible; grep the rest"], name)

    def test_an_alias_it_cannot_follow_is_still_named(self):
        self.write("al.py", "import elsewhere\nalias = elsewhere.helper\n")  # unresolved
        self.write("loc.py", "from pkg.core import helper\n\n\ndef go():\n    fn = helper\n"
                             "    return fn(1)\n")
        self.git("add", "-A")
        lines = self.calls("helper")
        self.assertIn("  al_user.py:2 call (alias alias)", lines)  # possible, not a caller
        self.assertIn("  loc.py:6 call (alias fn)", lines)
        self.assertEqual(lines[-2], "text: 6 occurrences of helper, 6 on lines listed above; "
                                    "renamed: alias, fn, h, public_helper; 14 possible; grep the "
                                    "rest")

    def test_the_text_line_never_claims_completeness_with_a_renamed_binding(self):
        for name in ("helper", "public_helper", "h", "alias"):
            text = [x for x in self.calls(name) if x.startswith("text: ")]
            self.assertEqual(len(text), 1, name)
            self.assertNotIn("all on lines", text[0], name)
            self.assertIn("grep", text[0], name)

    test_the_full_answer = test_a_qualified_name_finds_the_same_definition = None
    test_methods = test_nothing_found_still_ends_with_coverage = None
    test_several_names_one_coverage_line = test_map_pages_and_sensitive_files_are_not_counted = None
    test_the_cap_and_all = test_unreadable_python_is_named = None
    test_alias_of_an_unresolved_import_stays_possible = None
    test_assignment_and_attribute_reference = test_refusals = None
    test_deterministic_and_writes_nothing = test_a_stored_reference_is_no_complete_list = None


class Fixture(unittest.TestCase):
    """A temporary repository of the given files, with CallsTest's helpers."""
    files = {}
    calls, write, git = CallsTest.calls, CallsTest.write, CallsTest.git
    tearDown = CallsTest.tearDown

    def setUp(self):
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        for rel, text in self.files.items():
            self.write(rel, text)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.git("add", "-A")

    def text(self, *args):
        return [x for x in self.calls(*args) if x.startswith("text: ")]


class LookupTest(Fixture):
    """A literal getattr or lookup assigned to a name: the name is renamed, its calls possible."""
    files = {
        "pkg/__init__.py": "",
        "pkg/core.py": "def helper(x):\n    return x\n\n\nclass Box:\n    def size(self):\n"
                       "        return 1\n",
        "g.py": "from pkg import core\ng = getattr(core, \"helper\")\ng()\n",
        "d.py": "from pkg import core\nh = core.__dict__[\"helper\"]\nh()\n",
        "s.py": "class Thing:\n    def run(self):\n        fn = getattr(self, \"size\", None)\n"
                "        fn()\n",
        "o.py": "import operator\nfrom pkg import core\noperator.attrgetter(\"Box\")(core)\n",
    }

    def test_getattr_and_dict_lookups(self):
        lines = self.calls("helper")
        self.assertIn("callers: none found", lines)
        for line in ("  d.py:2 renamed to h", "  d.py:3 call (alias h)", "  g.py:2 getattr",
                     "  g.py:2 renamed to g", "  g.py:3 call (alias g)", "  d.py:2 string"):
            self.assertIn(line, lines)
        self.assertEqual(lines[-2], "text: 3 occurrences of helper, 3 on lines listed above; "
                                    "renamed: g, h; 8 possible; grep the rest")

    def test_getattr_with_a_default_on_self(self):
        lines = self.calls("Box.size")
        self.assertIn("  s.py:3 renamed to fn", lines)
        self.assertIn("  s.py:4 call (alias fn)", lines)
        self.assertIn("renamed: fn;", lines[-2])

    def test_attrgetter_is_possible(self):
        lines = self.calls("Box")
        self.assertIn("  o.py:3 string", lines)
        self.assertEqual(lines[-2], "text: 2 occurrences of Box, 2 on lines listed above; "
                                    "1 possible; grep the rest")


class UnreadTest(Fixture):
    """A tracked Python file the scan can't read is named, and the text line says so."""
    files = {"core.py": "def f():\n    pass\n\n\ndef g():\n    f()\n"}

    def test_a_big_file_and_a_nul_byte(self):
        self.assertEqual(self.text("f"), ["text: 2 occurrences of f, all on lines listed above "
                                          "(tracked files only)"])
        for name, data in (("big.py", b"f()\n" + b"#" * (600 * 1024) + b"\n"),
                           ("nul.py", b"f()\n\0\n")):
            with open(os.path.join(self.root, name), "wb") as fh:
                fh.write(data)
        self.git("add", "-A")
        lines = self.calls("f")
        self.assertEqual(lines[-3], "text: 2 occurrences of f, 2 on lines listed above; 2 Python "
                                    "files not parsed; grep the rest")
        self.assertEqual(lines[-2], "not parsed: big.py (unreadable, too large or not text), "
                                    "nul.py (unreadable, too large or not text)")


class CompletenessTest(Fixture):
    """"all on lines listed above" only with no possible entry, unparsed file, renamed name or
    cut section."""
    files = {"core.py": "def f():\n    pass\n\n\ndef g():\n    f()\n"}  # import lines are
    # `possible` too: an imported function never gets "all"

    def test_all_only_when_the_whitelist_holds(self):
        clean = "text: 2 occurrences of f, all on lines listed above (tracked files only)"
        self.assertEqual(self.text("f"), [clean])
        many = "from core import f\n" + "f()\n" * 45
        for label, rel, text, args, expected in (
                ("possible", "x.py", "def g(obj):\n    obj.f()\n", (), "; 1 possible;"),
                ("not parsed", "x.py", "def (:\n", (), "; 1 Python file not parsed;"),
                ("renamed", "x.py", "from core import f as g\ng()\n", (), "; renamed: g;"),
                ("shadowed", "x.py", "def g(f):\n    f()\n", (), "; 1 possible;"),
                ("cut", "x.py", many, (), "; 1 possible; cut (rerun with --all);"),
                ("cut, all", "x.py", many, ("--all",), "; 1 possible; grep the rest")):
            self.write(rel, text)
            self.git("add", "-A")
            line = self.text("f", *args)[0]
            self.assertNotIn("all on lines", line, label)
            self.assertIn(expected, line, label)
            self.assertTrue(line.endswith("; grep the rest"), label)
            os.remove(os.path.join(self.root, rel))
            self.git("add", "-A")
            self.assertEqual(self.text("f"), [clean], label)
        self.write("x.py", "import core\n" + "core.f()\n" * 39)  # 40 callers, no cut
        self.git("add", "-A")
        self.assertEqual(self.text("f"), ["text: 41 occurrences of f, all on lines listed above "
                                          "(tracked files only)"])


class ShadowTest(Fixture):
    """A bare-name call of a parameter or of a name assigned in its function or at module level
    is no confident caller."""
    files = {
        "core.py": "def helper():\n    pass\n",
        "a.py": "from core import helper\n\n\ndef p(helper):\n    helper()\n\n\n"
                "def q():\n    helper = print\n    helper()\n\n\ndef r():\n    helper()\n",
        "b.py": "from core import helper\nhelper = staticmethod(helper)\nhelper()\n",
    }

    def test_shadowed_calls_are_possible(self):
        lines = self.calls("helper")
        self.assertEqual(lines[lines.index("callers:"):lines.index("callers:") + 2],
                         ["callers:", "  a.py:14 in r"])
        for line in ("  a.py:5 call (shadowed)", "  a.py:10 call (shadowed)",
                     "  b.py:3 call (shadowed)"):
            self.assertIn(line, lines)


if __name__ == "__main__":
    unittest.main()
