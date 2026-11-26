#!/usr/bin/env bash
# The workspace of rc-l1-off-by-one: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'pager' 'Count the pages' '`page_count(total, size)` gives the number of pages that `total` items fill, `size` items a page.' \
  '`pager.py`, `tests/`' \
  '`page_count(7, 3)` is 3, `page_count(10, 5)` is 2 and `page_count(0, 5)` is 0'
cat > 'pager.py' <<'EOF'
"""Splits a list into pages."""


def page(items, number, size):
    """The items of page `number` (1-based), `size` items a page."""
    start = (number - 1) * size
    return items[start:start + size]
EOF
cat > 'tests/test_pager.py' <<'EOF'
import unittest

from pager import page


class PageTest(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(page([1, 2, 3, 4, 5], 1, 2), [1, 2])

    def test_last_page(self):
        self.assertEqual(page([1, 2, 3, 4, 5], 3, 2), [5])
EOF
rc_commit 00 'Base: pager'
rc_branch
cat > 'pager.py' <<'EOF'
"""Splits a list into pages."""


def page(items, number, size):
    """The items of page `number` (1-based), `size` items a page."""
    start = (number - 1) * size
    return items[start:start + size]


def page_count(total, size):
    """How many pages `total` items fill, `size` items a page."""
    return total // size + 1
EOF
cat > 'tests/test_pager.py' <<'EOF'
import unittest

from pager import page, page_count


class PageTest(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(page([1, 2, 3, 4, 5], 1, 2), [1, 2])

    def test_last_page(self):
        self.assertEqual(page([1, 2, 3, 4, 5], 3, 2), [5])

    def test_page_count(self):
        self.assertEqual(page_count(7, 3), 3)
EOF
rc_mark_done
rc_commit 10 'P1: Count the pages'
rc_publish
