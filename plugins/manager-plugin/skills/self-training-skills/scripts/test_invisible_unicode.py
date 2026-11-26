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
from test_skilltrain import LESSONS, RECORDS, SKILL, Fixture, run  # noqa: E402

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
                  0x115F, 0x1160, 0x3164, 0xFFA0, 0xFE00, 0xFE0F, 0xE0000, 0xE0041, 0xE007F,
                  0xE0100, 0xE01EF]
        for cp in points:
            self.assertEqual(skilltrain.invisible_chars("ab%scd" % chr(cp)), [(1, 3, cp)],
                             hex(cp))

    def test_neighbours_are_not(self):
        for cp in (0x200A, 0x200E, 0x200F, 0x2065, 0x2029, 0x202F, 0x206A, 0xFDFF, 0xFE10,
                   0xE0080, 0xE00FF, 0xE01F0, 0x1161, 0x3165, 0xFFA1, 0xA0, 0xAD):
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


# What `check` (not strict) allows in a project's skill text, each in a sentence of prose.
ALLOWED = (
    ("warning sign", "\u26a0\ufe0f"),
    ("red heart", "\u2764\ufe0f"),
    ("keycap one", "1\ufe0f\u20e3"),
    ("health worker", "\U0001F9D1\u200d\u2695\ufe0f"),
    ("flag of England", "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"),
    ("flag of Scotland", "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"),
    ("flag of Wales", "\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F"),
    ("Persian word with ZWNJ", "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"),
    ("Devanagari word with ZWJ", "\u0915\u094d\u200d\u0937"),
)


class CheckTest(Fixture):
    def check(self, text):
        self.write(".claude/skills/release-notes/SKILL.md",
                   SKILL.replace("Group them by area.", "Group them by area. %s" % text))
        return run("check", self.dir)

    def test_emoji_and_joiners_inside_words_pass(self):
        for name, text in ALLOWED:
            code, out = self.check("See %s here." % text)
            self.assertEqual(code, 0, (name, out))
            self.assertNotIn("invisible", out, name)
            self.assertTrue(skilltrain.invisible_chars(text), "strict reports %s" % name)

    def test_a_bidi_override_in_prose_is_a_problem(self):
        code, out = self.check("Never \u202eesrever\u202c this.")
        self.assertEqual(code, 1, out)
        self.assertIn(".claude/skills/release-notes/SKILL.md:19 holds invisible characters "
                      "(U+202E RIGHT-TO-LEFT OVERRIDE at column 30, U+202C POP DIRECTIONAL "
                      "FORMATTING at column 38)", out)

    def test_a_stray_tag_character_is_a_problem(self):
        code, out = self.check("A hidden\U000E0041 tag, a broken \U0001F3F4\U000E0067 flag.")
        self.assertEqual(code, 1, out)
        self.assertIn("U+E0041 TAG LATIN CAPITAL LETTER A at column 32, U+E0067 TAG LATIN SMALL "
                      "LETTER G at column 49", out)

    def test_only_the_three_rgi_flags_may_hold_tags(self):
        def flag(payload):
            return "\U0001F3F4" + "".join(chr(0xE0000 + ord(c)) for c in payload) + "\U000E007F"
        for payload in ("abcdefghijklmnopqrstuvwxyz", "GBSCT", "usca", "gbnir", "abcdef"):
            code, out = self.check("A %s flag." % flag(payload))
            self.assertEqual(code, 1, (payload, out))
            self.assertIn("SKILL.md:19 holds invisible characters", out, payload)
            self.assertIn("TAG LATIN", out, payload)
        code, out = self.check("Two flags %s%s here." % (flag("gbwls"), flag("gbeng")))
        self.assertEqual(code, 0, out)
        self.assertNotIn("invisible", out)

    def test_a_joiner_is_allowed_only_inside_a_non_ascii_word(self):
        for text in ("de\u013a\u200d\u0301ete", "del\u0301\u200d\u0301ete", "a\u0300\u200cb",
                     "\u00e0\u200cb", "\u200c\u0645", "\u0645\u200c"):
            code, out = self.check("See %s here." % text)
            self.assertEqual(code, 0, (text, out))
            self.assertIn("note: .claude/skills/release-notes/SKILL.md:19 holds invisible", out,
                          ascii(text))
        code, out = self.check("See \u0915\u094d\u200d\u0937 here.")
        self.assertNotIn("invisible", out)

    def test_a_joiner_before_a_mark_or_after_a_final_virama(self):
        """Sinhala touching form (letter, ZWJ, al-lakuna) and Malayalam old-style chillu (letter,
        virama, ZWJ at a word's end) pass; ASCII-adjacent joiners stay notes."""
        for text in ("\u0d9a\u200d\u0dca\u0dc2", "\u0d9a\u200d\u0dca",
                     "\u0d9a\u200c\u0dca", "\u0d28\u0d4d\u200d", "\u0d28\u0d4d\u200d, \u0d32",
                     "\u0d23\u0d4d\u200d."):
            code, out = self.check("See %s here." % text)
            self.assertEqual(code, 0, (ascii(text), out))
            self.assertNotIn("invisible", out, ascii(text))
            self.assertTrue(skilltrain.invisible_chars(text), "strict reports %s" % ascii(text))
        for text in ("de\u013a\u200d\u0301ete", "a\u200d\u0dca", "\u0d9a\u200d\u0dcax",
                     "n\u0d4d\u200d", "\u0d28\u0d4d\u200dx",
                     "\u0d28\u0d4d\u200d1", "\u0d28\u0d4d\u200c", "\u0d28\u200d",
                     "\u0d28\u0301\u200d"):
            code, out = self.check("See %s here." % text)
            self.assertEqual(code, 0, (ascii(text), out))
            self.assertIn("note: .claude/skills/release-notes/SKILL.md:19 holds invisible", out,
                          ascii(text))

    def test_reference_files_are_checked_too(self):
        refs = os.path.join(self.dir, "references")
        os.makedirs(refs)
        with open(os.path.join(refs, "x.md"), "w", encoding="utf-8") as fh:
            fh.write("# Notes\n\nPlain text.\n")
        clean_code, clean = run("check", self.dir)
        self.assertNotIn("invisible", clean)
        with open(os.path.join(refs, "x.md"), "w", encoding="utf-8") as fh:
            fh.write("# Notes\n\nA hidden\U000E0041\U000E0042 payload.\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn(".claude/skills/release-notes/references/x.md:3 holds invisible characters "
                      "(U+E0041 TAG LATIN CAPITAL LETTER A at column 9, U+E0042 TAG LATIN CAPITAL "
                      "LETTER B at column 10): they can hide text from a review", out)
        with open(os.path.join(refs, "x.md"), "w", encoding="utf-8") as fh:
            fh.write("# Notes\n\nA\u200bspace.\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, clean_code, out)  # a note: the exit code stays what it was
        self.assertIn("note: .claude/skills/release-notes/references/x.md:3 holds invisible", out)

    def test_a_variation_selector_supplement_character_is_a_note(self):
        code, out = self.check("See a\U000E0100b here.")
        self.assertEqual(code, 0, out)
        self.assertIn("note: .claude/skills/release-notes/SKILL.md:19 holds invisible characters "
                      "(U+E0100 VARIATION SELECTOR-17 at column 29)", out)

    def test_other_characters_are_notes_and_nothing_is_stripped(self):
        skill = SKILL.replace("Group them by area.", "Group them by\u200barea.")
        self.write(".claude/skills/release-notes/SKILL.md", skill)
        self.write(".claude/skills/release-notes/lessons.md",
                   LESSONS.replace("look for", "look\u2060for", 1))
        self.write("docs/vault/skills/release-notes/records.md",
                   RECORDS.replace("# release-notes", "# release-notes\u200d", 1))
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        lines = [ln for ln in out.splitlines() if "invisible characters" in ln]
        self.assertEqual(len(lines), 3, out)
        self.assertTrue(all(ln.startswith("note: ") for ln in lines), out)
        self.assertEqual(lines[0], "note: .claude/skills/release-notes/SKILL.md:19 holds invisible "
                         "characters (U+200B ZERO WIDTH SPACE at column 17): remove them unless "
                         "they belong there")
        self.assertIn("lessons.md:", lines[1])
        self.assertIn("records.md:", lines[2])
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
