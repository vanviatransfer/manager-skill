#!/usr/bin/env bash
# The workspace of rc-23: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'releases' 'Named version parts' '`parse_version` returns a dict '\
'with the parts `major`, `minor` and `patch` instead of a tuple, so code '\
'names the part it reads.' \
  '`versions.py`, the modules that use it, `tests/`' \
  '`parse_version("1.2.3")` gives `{"major": 1, "minor": 2, "patch": 3}` '\
'and still raises ValueError for a string that is not a version; every module '\
'that uses it keeps its behaviour'
cat > 'README.md' <<'EOF'
# releases

Helpers for the release process of a project: version numbers, release tags, the change log
and the release notes.

    python3 cli.py bump minor 1.4.2      # prints 1.5.0
    python3 cli.py newest 1.2.0 1.10.0   # prints 1.10.0
    python3 cli.py heading 1.5.0 2026-01-05

Run the tests with `python3 run_tests.py`.
EOF
cat > 'versions.py' <<'EOF'
"""Version strings of the form MAJOR.MINOR.PATCH."""


def parse_version(text):
    """The three parts of `text` ("1.2.3", an optional leading "v") as a tuple of ints;
    ValueError for a string that is not a version."""
    text = text.strip()
    if text.startswith("v"):
        text = text[1:]
    parts = text.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("not a version: %r" % text)
    return tuple(int(part) for part in parts)


def format_version(major, minor, patch):
    """The version string of three parts."""
    return "%d.%d.%d" % (major, minor, patch)
EOF
cat > 'compare.py' <<'EOF'
"""The order of version strings."""
from versions import parse_version


def is_newer(candidate, current):
    """Whether version `candidate` comes after version `current`."""
    return parse_version(candidate) > parse_version(current)


def newest(texts):
    """The highest of the version strings `texts`, None for none."""
    return max(texts, key=parse_version, default=None)
EOF
cat > 'release.py' <<'EOF'
"""The version number of the next release."""
from versions import format_version, parse_version

PARTS = ("major", "minor", "patch")


def bump(current, part):
    """The version after `current` that raises `part` (one of PARTS) by one and sets the parts
    after it to 0: bump("1.4.2", "minor") gives "1.5.0"."""
    if part not in PARTS:
        raise ValueError("not a version part: %r" % part)
    parsed = parse_version(current)
    major, minor, patch = parsed[0], parsed[1], parsed[2]
    if part == "major":
        return format_version(major + 1, 0, 0)
    if part == "minor":
        return format_version(major, minor + 1, 0)
    return format_version(major, minor, patch + 1)
EOF
cat > 'tags.py' <<'EOF'
"""Release tags: a version with a leading "v"."""
from versions import parse_version


def tag_name(version):
    """The tag of a version string: "1.2.3" gives "v1.2.3"."""
    return "v" + version


def is_release_tag(name):
    """Whether the tag `name` is a release tag ("v" and a version)."""
    if not name.startswith("v"):
        return False
    try:
        parse_version(name)
    except ValueError:
        return False
    return True


def release_tags(names):
    """The release tags among `names`, in their order."""
    return [name for name in names if is_release_tag(name)]
EOF
cat > 'changelog.py' <<'EOF'
"""Sections of the change log (CHANGELOG.md)."""


def heading(version, date):
    """The heading of a release's section: "## 1.5.0 (2026-01-05)"."""
    return "## %s (%s)" % (version, date)


def section(version, date, entries):
    """A release's section: its heading, then one bullet per entry, then an empty line."""
    lines = [heading(version, date), ""]
    lines += ["- " + entry.strip() for entry in entries if entry.strip()]
    return "\n".join(lines) + "\n\n"
EOF
cat > 'notes.py' <<'EOF'
"""The release notes file of a version."""
import os

NOTES_FOLDER = "release-notes"


def notes_path(version):
    """The path of a version's release notes: release-notes/1.5.0.md."""
    return os.path.join(NOTES_FOLDER, version + ".md")


def notes_title(version, name):
    """The first line of the release notes."""
    return "# %s %s" % (name, version)
EOF
cat > 'textutil.py' <<'EOF'
"""Small text helpers."""


def indent(text, spaces=2):
    """`text` with every non-empty line indented by `spaces` spaces."""
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.split("\n"))


def plural(count, word):
    """ "1 change", "2 changes"."""
    return "%d %s%s" % (count, word, "" if count == 1 else "s")
EOF
cat > 'cli.py' <<'EOF'
"""The command line: cli.py bump PART VERSION | newest VERSION... | heading VERSION DATE."""
import sys

import changelog
import compare
import release


def main(argv):
    if len(argv) == 4 and argv[1] == "bump":
        print(release.bump(argv[3], argv[2]))
    elif len(argv) > 2 and argv[1] == "newest":
        print(compare.newest(argv[2:]))
    elif len(argv) == 4 and argv[1] == "heading":
        print(changelog.heading(argv[2], argv[3]))
    else:
        print(__doc__.split(": ", 1)[1], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
EOF
cat > 'tests/test_versions.py' <<'EOF'
import unittest

from versions import format_version, parse_version


class ParseVersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version(" v10.0.7 "), (10, 0, 7))

    def test_not_a_version(self):
        for text in ("1.2", "1.2.x", "", "v", "1..3"):
            with self.subTest(text=text):
                self.assertRaises(ValueError, parse_version, text)

    def test_format(self):
        self.assertEqual(format_version(1, 5, 0), "1.5.0")
EOF
cat > 'tests/test_compare.py' <<'EOF'
import unittest

from compare import is_newer, newest


class CompareTest(unittest.TestCase):
    def test_is_newer(self):
        self.assertTrue(is_newer("1.10.0", "1.9.9"))
        self.assertFalse(is_newer("1.2.3", "1.2.3"))
        self.assertFalse(is_newer("0.9.0", "1.0.0"))

    def test_newest(self):
        self.assertEqual(newest(["1.2.0", "1.10.0", "1.9.0"]), "1.10.0")
        self.assertIsNone(newest([]))
EOF
cat > 'tests/test_tags.py' <<'EOF'
import unittest

from tags import is_release_tag, release_tags, tag_name


class TagsTest(unittest.TestCase):
    def test_tag_name(self):
        self.assertEqual(tag_name("1.2.3"), "v1.2.3")

    def test_release_tags(self):
        self.assertTrue(is_release_tag("v1.2.3"))
        self.assertFalse(is_release_tag("1.2.3"))
        self.assertFalse(is_release_tag("v1.2"))
        self.assertEqual(release_tags(["v1.0.0", "nightly", "v1.1.0"]), ["v1.0.0", "v1.1.0"])
EOF
cat > 'tests/test_changelog.py' <<'EOF'
import unittest

from changelog import heading, section


class ChangelogTest(unittest.TestCase):
    def test_heading(self):
        self.assertEqual(heading("1.5.0", "2026-01-05"), "## 1.5.0 (2026-01-05)")

    def test_section(self):
        self.assertEqual(section("1.5.0", "2026-01-05", ["Faster.", " ", "Smaller. "]),
                         "## 1.5.0 (2026-01-05)\n\n- Faster.\n- Smaller.\n\n")
EOF
cat > 'tests/test_notes.py' <<'EOF'
import os
import unittest

from notes import notes_path, notes_title


class NotesTest(unittest.TestCase):
    def test_notes(self):
        self.assertEqual(notes_path("1.5.0"), os.path.join("release-notes", "1.5.0.md"))
        self.assertEqual(notes_title("1.5.0", "releases"), "# releases 1.5.0")
EOF
cat > 'tests/test_textutil.py' <<'EOF'
import unittest

from textutil import indent, plural


class TextutilTest(unittest.TestCase):
    def test_indent(self):
        self.assertEqual(indent("a\n\nb"), "  a\n\n  b")

    def test_plural(self):
        self.assertEqual([plural(n, "change") for n in (0, 1, 2)],
                         ["0 changes", "1 change", "2 changes"])
EOF
cat > 'tests/test_cli.py' <<'EOF'
import contextlib
import io
import unittest

import cli


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["cli.py"] + list(args))
        return code, out.getvalue()

    def test_newest_and_heading(self):
        self.assertEqual(self.run_cli("newest", "1.2.0", "1.10.0"), (0, "1.10.0\n"))
        self.assertEqual(self.run_cli("heading", "1.5.0", "2026-01-05"),
                         (0, "## 1.5.0 (2026-01-05)\n"))

    def test_usage(self):
        self.assertEqual(self.run_cli("nothing")[0], 2)
EOF
rc_commit 00 'Base: releases'
rc_branch
cat > 'versions.py' <<'EOF'
"""Version strings of the form MAJOR.MINOR.PATCH."""


def parse_version(text):
    """The three parts of `text` ("1.2.3", an optional leading "v") as a dict with the keys
    "major", "minor" and "patch"; ValueError for a string that is not a version."""
    text = text.strip()
    if text.startswith("v"):
        text = text[1:]
    parts = text.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("not a version: %r" % text)
    major, minor, patch = (int(part) for part in parts)
    return {"major": major, "minor": minor, "patch": patch}


def format_version(major, minor, patch):
    """The version string of three parts."""
    return "%d.%d.%d" % (major, minor, patch)
EOF
cat > 'compare.py' <<'EOF'
"""The order of version strings."""
from versions import parse_version


def _order(text):
    """The sort key of a version string."""
    parts = parse_version(text)
    return parts["major"], parts["minor"], parts["patch"]


def is_newer(candidate, current):
    """Whether version `candidate` comes after version `current`."""
    return _order(candidate) > _order(current)


def newest(texts):
    """The highest of the version strings `texts`, None for none."""
    return max(texts, key=_order, default=None)
EOF
cat > 'tests/test_versions.py' <<'EOF'
import unittest

from versions import format_version, parse_version


class ParseVersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_version("1.2.3"), {"major": 1, "minor": 2, "patch": 3})
        self.assertEqual(parse_version(" v10.0.7 "), {"major": 10, "minor": 0, "patch": 7})

    def test_not_a_version(self):
        for text in ("1.2", "1.2.x", "", "v", "1..3"):
            with self.subTest(text=text):
                self.assertRaises(ValueError, parse_version, text)

    def test_format(self):
        self.assertEqual(format_version(1, 5, 0), "1.5.0")
EOF
rc_mark_done
rc_commit 10 'P1: Named version parts'
rc_publish
