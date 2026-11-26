#!/usr/bin/env bash
# The workspace of rc-21: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'posts' 'Hashtags' '`hashtags(text)` lists the hashtags of a post.' \
  '`tags.py`, `tests/`' \
  '`hashtags(text)` returns the normalized hashtags (`#word`) of `text`, '\
'each once, in the order they first appear'
cat > 'tags.py' <<'EOF'
"""Tags of posts."""


def normalize(tag):
    """`tag` lower-cased, without surrounding whitespace and trailing punctuation."""
    return tag.strip().rstrip(".,;:!?").lower()
EOF
cat > 'tests/test_tags.py' <<'EOF'
import unittest

from tags import normalize


class NormalizeTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize(" Python! "), "python")
EOF
rc_commit 00 'Base: posts'
rc_branch
cat > 'tags.py' <<'EOF'
"""Tags of posts."""


def normalize(tag):
    """`tag` lower-cased, without surrounding whitespace and trailing punctuation."""
    return tag.strip().rstrip(".,;:!?").lower()


def hashtags(text, seen=[]):
    """The hashtags of `text` (`#word`), normalized, each once, in order of first appearance."""
    for word in text.split():
        if word.startswith("#") and len(word) > 1:
            tag = normalize(word[1:])
            if tag and tag not in seen:
                seen.append(tag)
    return seen
EOF
cat > 'tests/test_tags.py' <<'EOF'
import unittest

from tags import hashtags, normalize


class NormalizeTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize(" Python! "), "python")


class HashtagsTest(unittest.TestCase):
    def test_hashtags(self):
        text = "New post on #Python and #testing, more #python soon. # #!"
        self.assertEqual(hashtags(text), ["python", "testing"])
EOF
rc_mark_done
rc_commit 10 'P1: Hashtags'
rc_publish
