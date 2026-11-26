"""Invisible or direction-changing characters: skilltrain.invisible_chars, the problems
`skilltrain.py check` reports with it, and a scan of the plugin's own text files and the
repository's docs. python3 -m unittest discover -s <this folder>"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.dirname(os.path.dirname(PLUGIN))  # plugins/manager-plugin in the repository
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import skilltrain  # noqa: E402
from test_skilltrain import LESSONS, SKILL, Fixture, run  # noqa: E402

SKIP_DIRS = {".git", "__pycache__", "node_modules"}


def text_files(top, skip=()):
    """The files under top that read as text (no NUL in their first 8 KiB), sorted."""
    found = []
    for folder, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and os.path.join(folder, d) not in skip)
        for name in sorted(files):
            path = os.path.join(folder, name)
            with open(path, "rb") as fh:
                head = fh.read(8192)
            if b"\0" not in head:
                found.append(path)
    return found


def findings(paths, base):
    out = []
    for path in paths:
        with open(path, "rb") as fh:
            text = fh.read().replace(b"\r\n", b"\n").decode("utf-8", "replace")
        rel = os.path.relpath(path, base).replace(os.sep, "/")
        out += ["%s:%d:%d: %s" % (rel, n, col, skilltrain.char_name(cp))
                for n, col, cp in skilltrain.invisible_chars(text)]
    return out


class HelperTest(unittest.TestCase):
    def test_every_listed_code_point_is_found(self):
        points = [0x200B, 0x200C, 0x200D, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF,
                  0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
                  0x115F, 0x1160, 0x3164, 0xFFA0, 0xFE00, 0xFE0F, 0xE0000, 0xE0041, 0xE007F]
        for cp in points:
            self.assertEqual(skilltrain.invisible_chars("ab%scd" % chr(cp)), [(1, 3, cp)],
                             hex(cp))

    def test_neighbours_are_not(self):
        for cp in (0x200A, 0x200E, 0x200F, 0x2065, 0x2029, 0x202F, 0x206A, 0xFDFF, 0xFE10,
                   0xE0080, 0x1161, 0x3165, 0xFFA1, 0xA0, 0xAD):
            self.assertEqual(skilltrain.invisible_chars("a%sb" % chr(cp)), [], hex(cp))
        text = "k\u0131sa tut \u2014 \u201cok\u201d \u2713 \U0001F916\n"
        self.assertEqual(skilltrain.invisible_chars(text), [])

    def test_lines_columns_and_a_leading_bom(self):
        text = "\ufeffone\ntw\u200bo\r\nthree \u202eevil\u202c\n\ufeff"
        self.assertEqual(skilltrain.invisible_chars(text),
                         [(2, 3, 0x200B), (3, 7, 0x202E), (3, 12, 0x202C), (4, 1, 0xFEFF)])

    def test_a_zwj_between_two_emoji_is_allowed(self):
        family = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
        self.assertEqual(skilltrain.invisible_chars("a %s b" % family), [])
        toned = "\U0001F469\U0001F3FD\u200d\U0001F4BB"  # a skin-tone modifier before the ZWJ
        self.assertEqual(skilltrain.invisible_chars(toned), [])
        heart = "\u2764\ufe0f\u200d\U0001F525"  # the selector is reported, the ZWJ is not
        self.assertEqual(skilltrain.invisible_chars(heart), [(1, 2, 0xFE0F)])
        for text, col in (("a\u200db", 2), ("\U0001F468\u200d", 2), ("\u200d\U0001F468", 1),
                          ("\U0001F468\u200dx", 2), ("x\u200d\U0001F468", 2)):
            self.assertEqual(skilltrain.invisible_chars(text), [(1, col, 0x200D)], text)

    def test_names(self):
        self.assertEqual(skilltrain.char_name(0x200B), "U+200B ZERO WIDTH SPACE")
        self.assertEqual(skilltrain.char_name(0xE0041), "U+E0041 TAG LATIN CAPITAL LETTER A")


class CheckTest(Fixture):
    def test_one_problem_per_file_and_line_nothing_stripped(self):
        skill = SKILL.replace("## Purpose", "## Purpose\u200b").replace(
            "Group them by area.", "Group \u202ethem\u202c by area.")
        self.write(".claude/skills/release-notes/SKILL.md", skill)
        self.write(".claude/skills/release-notes/lessons.md",
                   LESSONS.replace("| L1 |", "| L1\u2060 |", 1))
        self.append("docs/vault/skills/release-notes/records.md", "\u200d\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        lines = [ln for ln in out.splitlines() if "invisible characters" in ln]
        self.assertEqual(len(lines), 4, out)
        self.assertIn(".claude/skills/release-notes/SKILL.md:12 holds invisible characters "
                      "(U+200B ZERO WIDTH SPACE at column 11)", out)
        self.assertIn("(U+202E RIGHT-TO-LEFT OVERRIDE at column 10, U+202C POP DIRECTIONAL "
                      "FORMATTING at column 15)", out)
        self.assertIn("lessons.md:", lines[2])
        self.assertIn("records.md:", lines[3])
        with open(os.path.join(self.dir, "SKILL.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), skill)

    def test_a_clean_skill_and_a_leading_bom_pass(self):
        self.write(".claude/skills/release-notes/SKILL.md", "\ufeff" + SKILL)
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)


class PluginTextTest(unittest.TestCase):
    """No invisible or direction-changing character in the plugin's text files (skills, agents,
    references, hooks, scripts, evals) or in the repository's README and docs/."""

    def test_plugin_files(self):
        files = text_files(PLUGIN, skip={os.path.join(PLUGIN, "evals", "results")})
        self.assertGreater(len(files), 50)
        self.assertEqual(findings(files, PLUGIN), [])

    def test_repository_docs(self):
        if not os.path.isfile(os.path.join(REPO, ".claude-plugin", "marketplace.json")):
            self.skipTest("not in the plugin's repository (an installed copy)")
        files = [p for p in (os.path.join(REPO, name) for name in sorted(os.listdir(REPO)))
                 if os.path.isfile(p) and p.endswith(".md")]
        files += text_files(os.path.join(REPO, "docs"))
        self.assertTrue(files)
        self.assertEqual(findings(files, REPO), [])


if __name__ == "__main__":
    unittest.main()
