#!/usr/bin/env bash
# The workspace of rc-02: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'text' 'First word' '`first_word(text)` gives the first word of a text, or None.' \
  '`text.py`, `tests/`' \
  '`first_word("  hi there")` is `hi`; `first_word("")`, `first_word("   ")` and `first_word(None)` are None'
cat > 'tests/test_text.py' <<'EOF'
import unittest

from text import words


class WordsTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(words(" a b "), ["a", "b"])
        self.assertEqual(words(None), [])
EOF
cat > 'text.py' <<'EOF'
"""Text helpers."""


def words(text):
    """The words of `text`; none for None."""
    return (text or "").split()
EOF
rc_commit 00 'Base: text'
rc_branch
cat > 'tests/test_text.py' <<'EOF'
import unittest

from text import first_word, words


class WordsTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(words(" a b "), ["a", "b"])
        self.assertEqual(words(None), [])


class FirstWordTest(unittest.TestCase):
    def test_first_word(self):
        self.assertEqual(first_word("  hi there"), "hi")
        for text in ("", "   ", None):
            self.assertIsNone(first_word(text))
EOF
cat > 'text.py' <<'EOF'
"""Text helpers."""
import re


def words(text):
    """The words of `text`; none for None."""
    return (text or "").split()


def first_word(text):
    """The first word of `text`, or None."""
    match = re.match(r"\s*(\S+)", text or "")
    return match and match.group(1)
EOF
rc_mark_done
rc_commit 10 'P1: First word'
rc_publish
