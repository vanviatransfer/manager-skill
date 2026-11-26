#!/usr/bin/env bash
# The workspace of rc-l2-empty-input: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'stats' 'Mean' '`mean(values)` gives the arithmetic mean of a list of numbers.' \
  '`stats.py`, `tests/`' \
  '`mean([2, 4])` is 3.0; `mean([])` returns None instead of raising'
cat > 'stats.py' <<'EOF'
"""Small statistics over lists of numbers."""


def total(values):
    """The sum of the values; 0 for none."""
    return sum(values)
EOF
cat > 'tests/test_stats.py' <<'EOF'
import unittest

from stats import total


class TotalTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([1, 2, 3]), 6)
        self.assertEqual(total([]), 0)
EOF
rc_commit 00 'Base: stats'
rc_branch
cat > 'stats.py' <<'EOF'
"""Small statistics over lists of numbers."""


def total(values):
    """The sum of the values; 0 for none."""
    return sum(values)


def mean(values):
    """The arithmetic mean of the values."""
    return sum(values) / len(values)
EOF
cat > 'tests/test_stats.py' <<'EOF'
import unittest

from stats import mean, total


class TotalTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([1, 2, 3]), 6)
        self.assertEqual(total([]), 0)


class MeanTest(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([2, 4]), 3.0)
        self.assertEqual(mean([1]), 1.0)
EOF
rc_mark_done
rc_commit 10 'P1: Mean'
rc_publish
