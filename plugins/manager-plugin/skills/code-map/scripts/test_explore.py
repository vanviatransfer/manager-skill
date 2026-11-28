"""Tests for codemap.py `explore`.

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

CORE = (
    "import functools\n"                      # 1
    "\n"                                      # 2
    "\n"                                      # 3
    "def helper(x):\n"                        # 4
    "    return x + 1\n"                      # 5
    "\n"                                      # 6
    "\n"                                      # 7
    "class Box:\n"                            # 8
    "    \"\"\"A box.\"\"\"\n"                # 9
    "\n"                                      # 10
    "    def size(self):\n"                   # 11
    "        return helper(1)\n"              # 12
    "\n"                                      # 13
    "    @functools.lru_cache()\n"            # 14
    "    def cached(self):\n"                 # 15
    "        return self.size()\n"            # 16
    "\n"                                      # 17
    "\n"                                      # 18
    "@functools.lru_cache()\n"                # 19
    "@staticmethod\n"                         # 20
    "def decorated():\n"                      # 21
    "    return helper(2)\n"                  # 22
    "\n"                                      # 23
    "\n"                                      # 24
    "def outer():\n"                          # 25
    "    def inner():\n"                      # 26
    "        return 3\n"                      # 27
    "    return inner()\n")                   # 28

WEB = (
    "export function render(a) {\n"           # 1
    "  return a;\n"                           # 2
    "}\n"                                     # 3
    "\n"                                      # 4
    "export class View {\n"                   # 5
    "  show() {}\n"                           # 6
    "}\n")                                    # 7


class ExploreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        self.write("pkg/__init__.py", "")
        self.write("pkg/core.py", CORE)
        self.write("pkg/use.py", "from pkg.core import helper\n\n\ndef user():\n"
                   "    return helper(9)\n")
        self.write("web/view.ts", WEB)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.add()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def add(self):
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)

    def explore(self, *args):
        code, out = run("explore", *args, "--root", self.root)
        self.assertEqual(code, 0)
        return out.splitlines()

    def test_python_function_source_and_callers(self):
        self.assertEqual(self.explore("helper"), [
            "explore helper: 1 definition in 1 file",
            "pkg/core.py:4-5 function helper",
            "4\tdef helper(x):",
            "5\t    return x + 1",
            "callers:",
            "  pkg/core.py:12 in Box.size",
            "  pkg/core.py:22 in decorated",
            "  pkg/use.py:5 in user",
            "possible: 1 (calls helper lists them)",  # the import in use.py
        ])

    def test_method_and_module_qualified(self):
        out = self.explore("Box.size")
        self.assertEqual(out[1:4], ["pkg/core.py:11-12 method Box.size",
                                    "11\t    def size(self):", "12\t        return helper(1)"])
        self.assertIn("  pkg/core.py:16 in Box.cached", out)
        self.assertEqual(self.explore("pkg.core.helper")[1], "pkg/core.py:4-5 function helper")
        self.assertIn("no definition named other.helper", self.explore("other.helper")[0])

    def test_decorated_starts_at_first_decorator(self):
        out = self.explore("decorated")
        self.assertEqual(out[1], "pkg/core.py:19-22 function decorated")
        self.assertEqual(out[2], "19\t@functools.lru_cache()")
        self.assertEqual(self.explore("cached")[1], "pkg/core.py:14-16 method Box.cached")

    def test_nested_name(self):
        out = self.explore("outer.inner")
        self.assertEqual(out[1:3], ["pkg/core.py:26-27 function outer.inner",
                                    "26\t    def inner():"])
        self.assertIn("  pkg/core.py:28 in outer", out)

    def test_class_over_budget_lists_members(self):
        out = self.explore("Box", "--budget", "300")
        self.assertEqual(out[1:6], [
            "pkg/core.py:8-16 class Box",
            " 8\tclass Box:",  # padded to the widest number of the range
            "  11-12 method Box.size",
            "  14-16 method Box.cached",
            "body not shown: read pkg/core.py:9-16",
        ])
        self.assertFalse(any(line.startswith("cut:") for line in out))

    def test_function_over_budget_first_lines_then_pointer(self):
        body = "".join("    x%d = %d\n" % (n, n) for n in range(200))
        self.write("pkg/big.py", "def big():\n" + body + "    return 0\n")
        self.add()
        out = self.explore("big", "--budget", "600")
        self.assertEqual(out[1], "pkg/big.py:1-202 function big")
        self.assertEqual(out[2], "  1\tdef big():")
        pointer = [line for line in out if line.startswith("body not shown")]
        self.assertEqual(len(pointer), 1)
        shown = int(out[out.index(pointer[0]) - 1].split("\t")[0])
        self.assertEqual(pointer[0], "body not shown: read pkg/big.py:%d-202" % (shown + 1))
        self.assertLessEqual(sum(len(line) + 1 for line in out), 600)

    def test_js_ts_approximate_end_and_callers_line(self):
        out = self.explore("render")
        self.assertEqual(out, [
            "explore render: 1 definition in 1 file",
            "web/view.ts:1-3 function render (end approximate)",
            "1\texport function render(a) {",
            "2\t  return a;",
            "3\t}",
            "callers: not resolved for TypeScript; grep -n -w render",
        ])
        self.assertEqual(self.explore("View")[1], "web/view.ts:5-7 class View (end approximate)")
        self.assertEqual(self.explore("view.render")[1][:15], "web/view.ts:1-3")

    def test_no_match_lists_near_matches(self):
        out = self.explore("help")
        self.assertEqual(out, ["explore help: no definition named help; near matches:",
                               "  pkg/core.py:4 helper"])
        self.assertEqual(self.explore("helpr")[1:], ["  pkg/core.py:4 helper"])  # a typo
        self.assertEqual(self.explore("zzzz"),
                         ["explore zzzz: no definition named zzzz; near matches: none found"])
        for n in range(8):
            self.write("pkg/h%d.py" % n, "def helper_%d():\n    pass\n" % n)
        self.add()
        self.assertEqual(len(self.explore("help")), 1 + 5)

    def test_several_definitions_headers_only(self):
        for n in range(4):
            self.write("pkg/m%d.py" % n, "def helper():\n    return %d\n" % n)
        self.add()
        out = self.explore("helper")
        self.assertIn("5 definitions in 5 files; more than 3 files: headers only, no source",
                      out[0])
        self.assertEqual(out[1:6], ["pkg/core.py:4-5 function helper"]
                         + ["pkg/m%d.py:1-2 function helper" % n for n in range(4)])
        self.assertFalse(any("\t" in line for line in out))
        out = self.explore("helper", "--budget", "400")  # some headers cut, listed
        self.assertTrue(any(line.startswith("cut: pkg/m") for line in out))
        self.assertIn("over the budget of 400 characters (--budget):", out)

    def test_budget_cut_lists_ranges(self):
        out = self.explore("helper", "decorated", "Box.size", "--budget", "330")
        cut = [line for line in out if line.startswith("cut: ")]
        self.assertTrue(cut)
        self.assertTrue(all(":" in line[5:] and "-" in line for line in cut))
        self.assertEqual(out[-len(cut) - 1], "over the budget of 330 characters (--budget):")
        self.assertNotIn("all", " ".join(out).split())
        total = self.explore("helper", "decorated", "Box.size")
        self.assertFalse(any(line.startswith("cut:") for line in total))

    def test_callers_cap(self):
        calls = "".join("def c%d():\n    return helper(%d)\n\n\n" % (n, n) for n in range(14))
        self.write("pkg/many.py", "from pkg.core import helper\n\n\n" + calls)
        self.add()
        out = self.explore("helper")
        listed = [line for line in out if " in " in line and line.startswith("  ")]
        self.assertEqual(len(listed), codemap.EXPLORE_CALLERS)
        self.assertIn("  more: 7; run calls helper", out)  # 17 resolved

    def test_unparsed_python_is_approximate(self):
        self.write("pkg/broken.py", "def broken(:\n    pass\n\n\ndef after():\n    pass\n")
        self.add()
        out = self.explore("broken")
        self.assertEqual(out[1], "pkg/broken.py:1-2 function broken (end approximate; not "
                                 "parsed: syntax error, line 1)")
        self.assertIn("callers: not resolved in Python files not parsed; grep -n -w broken", out)

    def test_bad_name_and_flags(self):
        for argv in (["explore"], ["explore", "a-b"], ["explore", "x", "--budget", "0"],
                     ["explore", "x", "--all"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                run(*argv, "--root", self.root)

    def test_writes_nothing(self):
        before = subprocess.run(["git", "-C", self.root, "status", "--porcelain"],
                                capture_output=True, check=True).stdout
        self.explore("helper", "Box")
        after = subprocess.run(["git", "-C", self.root, "status", "--porcelain"],
                               capture_output=True, check=True).stdout
        self.assertEqual(before, after)
        self.assertFalse(os.path.exists(os.path.join(self.root, codemap.CONFIG)))


if __name__ == "__main__":
    unittest.main()
