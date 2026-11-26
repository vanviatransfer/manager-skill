#!/usr/bin/env bash
# The workspace of rc-05: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'slugs' 'Slug separator' '`slugify(text, sep="-")` joins the words of a slug with `sep`.' \
  '`slug.py`, `tests/`' \
  '`slugify("a b", sep="_")` is `a_b`; the default separator stays `-`'
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


def slugify(text, sep="-"):
    """`text` lower-cased, each run of other characters than a-z and 0-9 as one `sep`."""
    return sep.join(re.findall(r"[a-z0-9]+", text.lower()))
EOF
cat > 'tests/slug_test.py' <<'EOF'
import unittest

from slug import slugify


class SlugifyTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_separator(self):
        self.assertEqual(slugify("a b", sep="_"), "a_b")
EOF
git rm -q 'tests/test_slug.py'
rc_mark_done
rc_commit 10 'P1: Slug separator'
rc_publish
