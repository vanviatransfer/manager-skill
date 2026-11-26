#!/usr/bin/env bash
# The workspace of rc-clean-clamp: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'bounds' 'Clamp' '`clamp(x, lo, hi)` limits a number to a range.' \
  '`bounds.py`, `tests/`' \
  '`clamp(x, lo, hi)` is `lo` below the range, `hi` above it and `x` inside (ends included); `lo > hi` raises ValueError'
cat > 'bounds.py' <<'EOF'
"""Numeric ranges."""


def between(x, lo, hi):
    """Whether lo <= x <= hi."""
    return lo <= x <= hi
EOF
cat > 'tests/test_bounds.py' <<'EOF'
import unittest

from bounds import between


class BetweenTest(unittest.TestCase):
    def test_between(self):
        self.assertTrue(between(5, 1, 5))
        self.assertFalse(between(6, 1, 5))
EOF
rc_commit 00 'Base: bounds'
rc_branch
cat > 'bounds.py' <<'EOF'
"""Numeric ranges."""


def between(x, lo, hi):
    """Whether lo <= x <= hi."""
    return lo <= x <= hi


def clamp(x, lo, hi):
    """`x` limited to lo..hi; ValueError when lo > hi."""
    if lo > hi:
        raise ValueError("lo is above hi")
    return min(max(x, lo), hi)
EOF
cat > 'tests/test_bounds.py' <<'EOF'
import unittest

from bounds import between, clamp


class BetweenTest(unittest.TestCase):
    def test_between(self):
        self.assertTrue(between(5, 1, 5))
        self.assertFalse(between(6, 1, 5))


class ClampTest(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual([clamp(x, 1, 5) for x in (0, 1, 3, 5, 6)], [1, 1, 3, 5, 5])

    def test_empty_range(self):
        self.assertRaises(ValueError, clamp, 3, 5, 1)
EOF
rc_mark_done
rc_commit 10 'P1: Clamp'
rc_publish
