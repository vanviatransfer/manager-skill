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
            codemap.EXPLORE_CURRENT,
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
        self.assertEqual(out[-1], codemap.EXPLORE_CURRENT)  # not counted, as the cut lines
        self.assertLessEqual(sum(len(line) + 1 for line in out[:-1]), 600)

    def test_js_ts_approximate_end_and_callers_line(self):
        out = self.explore("render")
        self.assertEqual(out, [
            "explore render: 1 definition in 1 file",
            "web/view.ts:1-3 function render (end approximate)",
            "1\texport function render(a) {",
            "2\t  return a;",
            "3\t}",
            "callers: not resolved for TypeScript; grep -n -w render",
            codemap.EXPLORE_CURRENT,
        ])
        self.assertEqual(self.explore("View")[1], "web/view.ts:5-7 class View (end approximate)")
        self.assertEqual(self.explore("view.render")[1][:15], "web/view.ts:1-3")

    def test_no_match_lists_near_matches(self):
        out = self.explore("help")
        self.assertEqual(out, ["explore help: no definition named help (TypeScript: only mapped "
                               "symbols searched; grep -n -w help); near matches:",
                               "  pkg/core.py:4 helper"])
        self.assertEqual(self.explore("helpr")[1:], ["  pkg/core.py:4 helper"])  # a typo
        self.assertEqual(self.explore("zzzz"),
                         ["explore zzzz: no definition named zzzz (TypeScript: only mapped "
                          "symbols searched; grep -n -w zzzz); near matches: none found"])
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

    def test_every_definition_of_one_qualified_name(self):
        self.write("pkg/many.py", (
            "from typing import overload\n"             # 1
            "\n"                                        # 2
            "\n"                                        # 3
            "@overload\n"                               # 4
            "def conv(x: int) -> int: ...\n"            # 5
            "@overload\n"                               # 6
            "def conv(x: str) -> str: ...\n"            # 7
            "def conv(x):\n"                            # 8
            "    return x\n"                            # 9
            "\n"                                        # 10
            "\n"                                        # 11
            "class Outer:\n"                            # 12
            "    @property\n"                           # 13
            "    def val(self):\n"                      # 14
            "        return 1\n"                        # 15
            "\n"                                        # 16
            "    @val.setter\n"                         # 17
            "    def val(self, v):\n"                   # 18
            "        pass\n"                            # 19
            "\n"                                        # 20
            "\n"                                        # 21
            "if True:\n"                                # 22
            "    def cond():\n"                         # 23
            "        return 1\n"                        # 24
            "else:\n"                                   # 25
            "    def cond():\n"                         # 26
            "        return 2\n"))                      # 27
        self.add()
        out = self.explore("conv")
        self.assertEqual(out[0], "explore conv: 3 definitions in 1 file")
        self.assertEqual([line for line in out if line.startswith("pkg/")], [
            "pkg/many.py:4-5 function conv", "pkg/many.py:6-7 function conv",
            "pkg/many.py:8-9 function conv"])
        out = self.explore("Outer.val")
        self.assertEqual([line for line in out if line.startswith("pkg/")], [
            "pkg/many.py:13-15 method Outer.val", "pkg/many.py:17-19 method Outer.val"])
        out = self.explore("Outer", "--budget", "290")  # members once each, setter included
        self.assertEqual([line for line in out if line.startswith("  1")],
                         ["  13-15 method Outer.val", "  17-19 method Outer.val"], out)
        out = self.explore("cond")
        self.assertEqual([line for line in out if line.startswith("pkg/")], [
            "pkg/many.py:23-24 function cond", "pkg/many.py:26-27 function cond"])

    def test_lone_carriage_returns_count_as_ast_counts_them(self):
        with open(os.path.join(self.root, "pkg", "cr.py"), "w", encoding="utf-8",
                  newline="") as fh:
            fh.write("x = 1\r\rdef old_mac():\r    return 1\r")
        self.add()
        out = self.explore("old_mac")
        self.assertEqual(out[1:4], ["pkg/cr.py:3-4 function old_mac (lines counted as Python "
                                    "counts them; the Read tool sees this file differently)",
                                    "3\tdef old_mac():", "4\t    return 1"])
        self.assertEqual(out[-1], codemap.EXPLORE_INEXACT)
        e = {"path": "a.py", "start": 3, "end": 9, "kind": "function", "name": "f",
             "lines": ["", "", "def f():"], "note": ""}
        self.assertIn("(past the end of the file: it has 3 lines)", codemap.explore_header(e))

    def test_files_not_read_are_counted(self):
        self.write("pkg/huge.py", "def huge():\n" + "    x = 1\n" * 60000)  # over 512 KB
        self.write("vendor/lib.js", "export function vend() {}\n")
        self.add()
        out = self.explore("helper")
        self.assertIn(codemap.explore_unread(2), out)
        self.assertEqual(self.explore("huge")[0], "explore huge: no definition named huge (2 "
                         "tracked source files not read; TypeScript: only mapped symbols "
                         "searched; grep -n -w huge); near matches: none found")

    def test_approximate_end_not_found_within_the_cap(self):
        body = "".join("  a%d();\n" % n for n in range(400))
        self.write("web/big.ts", "export function big() {\n" + body + "}\n")
        self.add()
        out = self.explore("big", "--budget", "500")
        self.assertEqual(out[1], "web/big.ts:1-300 function big (end approximate; end not "
                                 "found within 300 lines)")
        self.assertTrue(any(line.startswith("body not shown: read web/big.ts from line ")
                            and line.endswith("; end not found within 300 lines") for line in out))
        out = self.explore("big", "--budget", "20000")
        self.assertIn("end not found within 300 lines: read web/big.ts from line 301", out)

    def test_near_the_limit_shortened_not_cut(self):
        sig = "".join("        argument_number_%d,\n" % n for n in range(6))
        self.write("pkg/wide.py", "def wide(\n" + sig + "):\n    return 0\n")
        self.add()
        full = self.explore("wide")
        header = "pkg/wide.py:1-9 function wide"
        pointer = "body not shown: read pkg/wide.py:1-9"
        fixed = [line for line in full if not line.startswith(("pkg/", " ", "body"))
                 and "\t" not in line and line != codemap.EXPLORE_CURRENT]
        budget = sum(len(line) + 1 for line in fixed + [header, pointer]) + 10
        out = self.explore("wide", "--budget", str(budget))  # no room for the signature
        self.assertIn(header, out)
        self.assertIn(pointer, out)
        self.assertFalse(any(line.startswith("cut:") for line in out))

    def test_members_under_if_try_with(self):
        self.write("pkg/cls.py", (
            "class C:\n"                                 # 1
            "    try:\n"                                 # 2
            "        def t(self):\n"                     # 3
            "            return 1\n"                     # 4
            "    except ImportError:\n"                  # 5
            "        def t(self):\n"                     # 6
            "            return 2\n"                     # 7
            "    with open('x') as f:\n"                 # 8
            "        def w(self):\n"                     # 9
            "            pass\n"                         # 10
            "    if True:\n"                             # 11
            "        def i(self):\n"                     # 12
            "            pass\n"                         # 13
            "\n"                                         # 14
            "    def plain(self):\n"                     # 15
            "        pass\n"))                           # 16
        self.add()
        out = self.explore("C", "--budget", "320")
        self.assertEqual([line for line in out if line.startswith("  ") and "-" in line[:8]], [
            "  3-4 method C.t", "  6-7 method C.t", "  9-10 method C.w",
            "  12-13 method C.i", "  15-16 method C.plain"], out)

    def test_class_signature_stops_before_a_decorated_member(self):
        self.write("pkg/dec.py", (
            "class D(\n"                                 # 1
            "    object,\n"                              # 2
            "):\n"                                       # 3
            "    @property\n"                            # 4
            "    def p(self):\n"                         # 5
            "        return 1\n"                         # 6
            + "".join("\n    def m%d(self):\n        return %d\n" % (n, n) for n in range(9))))
        self.add()
        out = self.explore("D", "--budget", "500")
        start = out.index("pkg/dec.py:1-33 class D")
        self.assertEqual(out[start + 1:start + 5], [
            " 1\tclass D(", " 2\t    object,", " 3\t):", "  4-6 method D.p"], out)
        self.assertIn("body not shown: read pkg/dec.py:4-33", out)

    def test_multi_line_signature_with_its_body_on_the_last_line(self):
        self.write("pkg/sig.py", "def s(a,\n      b): return (a +\n" + "    b)\n" * 30)
        self.add()
        out = self.explore("s", "--budget", "330")
        self.assertEqual(out[2:4], [" 1\tdef s(a,", " 2\t      b): return (a +"], out)
        self.assertTrue(any(line.startswith("body not shown: read pkg/sig.py:") for line in out))

    def test_no_match_counts_files_without_symbols(self):
        self.write("src/lib.c", "int qqq_c(void) { return 0; }\n")
        self.write("pkg/stub.pyi", "def zz() -> int: ...\n")
        self.add()
        self.assertEqual(self.explore("qqq_c")[0],
                         "explore qqq_c: no definition named qqq_c (TypeScript: only mapped "
                         "symbols searched; grep -n -w qqq_c; 2 files in languages without "
                         "symbols: grep them); near matches: none found")

    def test_inexact_source_says_so(self):
        with open(os.path.join(self.root, "pkg", "bytes.py"), "wb") as fh:
            fh.write(b"def odd():\n    return '\xff\x01'\n")
        self.add()
        out = self.explore("odd")
        self.assertEqual(out[-1], codemap.EXPLORE_INEXACT)
        self.assertEqual(self.explore("helper")[-1], codemap.EXPLORE_CURRENT)

    def test_many_cuts_of_one_name_in_one_file(self):
        self.write("pkg/ov.py", "from typing import overload\n\n" + "".join(
            "@overload\ndef ov(x: 'T%d') -> int: ...\n" % n for n in range(45)))
        self.add()
        out = self.explore("ov", "--budget", "100")
        tail = [line for line in out if line.startswith("cut: ") and "more" in line]
        self.assertEqual(tail, ["cut: 5 more definitions of ov in pkg/ov.py not listed; read "
                                "pkg/ov.py, raise --budget or grep -n -w ov"])

    def test_bom_file_parses(self):
        self.write("pkg/bom.py", "\ufeffdef bomf():\n    return 1\n\n\nclass B:\n"
                   "    def bm(self):\n        return bomf()\n")
        self.add()
        out = self.explore("bomf")
        self.assertEqual(out[1:3], ["pkg/bom.py:1-2 function bomf", "1\tdef bomf():"])
        self.assertIn("  pkg/bom.py:7 in B.bm", out)
        self.assertEqual(self.explore("B.bm")[1], "pkg/bom.py:6-7 method B.bm")
        self.assertFalse(any(line.startswith("not parsed") for line in out))
        code, calls = run("calls", "bomf", "--root", self.root)  # calls: as before, not parsed
        self.assertIn("not parsed: pkg/bom.py", calls)

    def test_unparsed_files_are_counted(self):
        self.write("pkg/bad.py", "class K:\n    def meth(self):\n        return (\n")
        self.write("pkg/ok.py", "def meth():\n    pass\n")
        self.add()
        out = self.explore("meth")
        self.assertEqual(out[0], "explore meth: 1 definition in 1 file")
        self.assertIn("not parsed: " + codemap.explore_unparsed(1), out)
        self.assertIn("(" + codemap.explore_unparsed(1) + "; TypeScript: only mapped symbols "
                      "searched; grep -n -w zork)", self.explore("zork")[0])

    def test_broken_pipe_exits_quietly(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codemap.py")
        body = "".join("    x%d = %d\n" % (n, n) for n in range(3000))
        self.write("pkg/long.py", "def long():\n" + body)
        self.add()
        proc = subprocess.Popen([sys.executable, script, "explore", "long", "--budget",
                                 "200000", "--root", self.root],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdout.readline()
        proc.stdout.close()
        err = proc.stderr.read()
        proc.stderr.close()
        self.assertEqual(proc.wait(), 0)
        self.assertNotIn(b"Traceback", err)

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
