#!/usr/bin/env bash
# The workspace of rc-24: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'people' 'Initials' '`initials(name)` gives the initials of a person'"'"'s name.' \
  '`names.py`, `tests/`' \
  '`initials(name)` gives the upper-case first letter of each word of `name` '\
'(words split at any whitespace), `""` for a name without words'
cat > 'names.py' <<'EOF'
"""Names of people."""


def full_name(first, last):
    """ "Ada Lovelace" from "Ada" and "Lovelace", without surrounding whitespace."""
    return ("%s %s" % (first.strip(), last.strip())).strip()
EOF
cat > 'tests/test_names.py' <<'EOF'
import unittest

from names import full_name


class FullNameTest(unittest.TestCase):
    def test_full_name(self):
        self.assertEqual(full_name(" Ada", "Lovelace "), "Ada Lovelace")
        self.assertEqual(full_name("", "Hopper"), "Hopper")
EOF
rc_commit 00 'Base: people'
rc_branch
cat > 'names.py' <<'EOF'
"""Names of people."""


def full_name(first, last):
    """ "Ada Lovelace" from "Ada" and "Lovelace", without surrounding whitespace."""
    return ("%s %s" % (first.strip(), last.strip())).strip()


def initials(name):
    """The upper-case first letter of each word of `name`: "Ada Lovelace" gives "AL". Words
    are seperated by any whitespace; a name without words gives ""."""
    return "".join(word[0].upper() for word in name.split())
EOF
cat > 'tests/test_names.py' <<'EOF'
import unittest

from names import full_name, initials


class FullNameTest(unittest.TestCase):
    def test_full_name(self):
        self.assertEqual(full_name(" Ada", "Lovelace "), "Ada Lovelace")
        self.assertEqual(full_name("", "Hopper"), "Hopper")


class InitialsTest(unittest.TestCase):
    def test_initials(self):
        self.assertEqual(initials("Ada Lovelace"), "AL")
        self.assertEqual(initials("grace brewster hopper"), "GBH")

    def test_any_whitespace(self):
        self.assertEqual(initials("  Ada \t King\nLovelace  "), "AKL")

    def test_no_words(self):
        self.assertEqual(initials(""), "")
        self.assertEqual(initials(" \t "), "")
EOF
rc_mark_done
rc_commit 10 'P1: Initials'
rc_publish
