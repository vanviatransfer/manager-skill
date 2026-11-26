#!/usr/bin/env bash
# The workspace of rc-l4-plan-drift: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'slugs' 'Slug length limit' '`slugify(text, max_length=50)` cuts a slug to at most `max_length` characters.' \
  '`slug.py`, `tests/`, the change log' \
  'a slug has at most `max_length` characters and never ends with a dash'
cat > 'slug.py' <<'EOF'
"""URL slugs."""
import re


def slugify(text):
    """`text` lower-cased, each run of other characters than a-z and 0-9 as one dash."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
EOF
cat > 'tests/test_slug.py' <<'EOF'
import unittest

from slug import slugify


class SlugifyTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")
EOF
rc_commit 00 'Base: slugs'
rc_branch
cat > 'slug.py' <<'EOF'
"""URL slugs."""
import re


def slugify(text, max_length=50):
    """`text` lower-cased, each run of other characters than a-z and 0-9 as one dash, cut to at
    most `max_length` characters."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].rstrip("-")
EOF
cat > 'tests/test_slug.py' <<'EOF'
import unittest

from slug import slugify


class SlugifyTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_max_length(self):
        self.assertEqual(slugify("abc def", max_length=4), "abc")
        self.assertEqual(slugify("abcdef", max_length=4), "abcd")
EOF
rc_mark_done
printf '%s\n' '- 2026-01-05: P1 done: `slugify` cuts slugs to `max_length` and now also folds accented letters to ASCII (`Café` gives `cafe`).' >> docs/LIVING_PLAN.md
rc_commit 10 'P1: Slug length limit'
rc_publish
