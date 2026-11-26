#!/usr/bin/env bash
# The workspace of rc-29: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'measures' 'Summary' '`summary(values)` gives the smallest value, '\
'the largest and the median of a list of numbers.' \
  '`stats.py`, `tests/`' \
  '`summary(values)` of a non-empty list gives `{"min": ..., "max": ..., '\
'"median": ...}` and leaves `values` as it was; an empty list raises ValueError'
cat > 'stats.py' <<'EOF'
"""Statistics of lists of numbers."""


def mean(values):
    """The arithmetic mean of a non-empty list; ValueError for an empty one."""
    if not values:
        raise ValueError("no values")
    return sum(values) / len(values)
EOF
cat > 'tests/test_stats.py' <<'EOF'
import unittest

from stats import mean


class MeanTest(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([1, 2, 6]), 3)
        self.assertRaises(ValueError, mean, [])
EOF
rc_commit 00 'Base: measures'
rc_branch
cat > 'stats.py' <<'EOF'
"""Statistics of lists of numbers."""


def mean(values):
    """The arithmetic mean of a non-empty list; ValueError for an empty one."""
    if not values:
        raise ValueError("no values")
    return sum(values) / len(values)


def summary(values):
    """The smallest value, the largest and the median of a non-empty list; ValueError for an
    empty one."""
    if not values:
        raise ValueError("no values")
    ordered = values
    ordered.sort()
    return {"min": ordered[0], "max": ordered[-1], "median": ordered[len(ordered) // 2]}
EOF
cat > 'tests/test_stats.py' <<'EOF'
import unittest

from stats import mean, summary


class MeanTest(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([1, 2, 6]), 3)
        self.assertRaises(ValueError, mean, [])


class SummaryTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(summary([7, 1, 4]), {"min": 1, "max": 7, "median": 4})
        self.assertEqual(summary([2.5]), {"min": 2.5, "max": 2.5, "median": 2.5})
        self.assertEqual(summary([9, -3, 0, 5, 1]), {"min": -3, "max": 9, "median": 1})

    def test_empty(self):
        self.assertRaises(ValueError, summary, [])
EOF
rc_mark_done
rc_commit 10 'P1: Summary'
rc_publish
