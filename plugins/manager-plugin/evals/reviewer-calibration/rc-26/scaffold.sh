#!/usr/bin/env bash
# The workspace of rc-26: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'dates' 'Month lengths' '`days_in_month(year, month)` gives the length of a month.' \
  '`months.py`, `tests/`' \
  '`days_in_month(year, month)` gives the number of days of `month` (1-12) '\
'in `year` of the Gregorian calendar, and raises ValueError for a month '\
'outside 1-12'
cat > 'months.py' <<'EOF'
"""Months of the year."""

NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December")


def month_name(month):
    """The English name of `month` (1-12)."""
    if not 1 <= month <= 12:
        raise ValueError("not a month: %r" % month)
    return NAMES[month - 1]
EOF
cat > 'tests/test_months.py' <<'EOF'
import unittest

from months import month_name


class MonthNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(month_name(1), "January")
        self.assertEqual(month_name(12), "December")
        self.assertRaises(ValueError, month_name, 13)
EOF
rc_commit 00 'Base: dates'
rc_branch
cat > 'months.py' <<'EOF'
"""Months of the year."""

NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December")
LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def month_name(month):
    """The English name of `month` (1-12)."""
    if not 1 <= month <= 12:
        raise ValueError("not a month: %r" % month)
    return NAMES[month - 1]


def days_in_month(year, month):
    """The number of days of `month` (1-12) in `year`."""
    if not 1 <= month <= 12:
        raise ValueError("not a month: %r" % month)
    return LENGTHS[month - 1]
EOF
cat > 'tests/test_months.py' <<'EOF'
import unittest

from months import days_in_month, month_name


class MonthNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(month_name(1), "January")
        self.assertEqual(month_name(12), "December")
        self.assertRaises(ValueError, month_name, 13)


class DaysInMonthTest(unittest.TestCase):
    def test_lengths(self):
        self.assertEqual(days_in_month(2025, 1), 31)
        self.assertEqual(days_in_month(2025, 4), 30)
        self.assertEqual(days_in_month(2025, 12), 31)

    def test_february(self):
        self.assertEqual(days_in_month(2023, 2), 28)
        self.assertEqual(days_in_month(1900, 2), 28)

    def test_not_a_month(self):
        self.assertRaises(ValueError, days_in_month, 2025, 0)
        self.assertRaises(ValueError, days_in_month, 2025, 13)
EOF
rc_mark_done
rc_commit 10 'P1: Month lengths'
cat > 'months.py' <<'EOF'
"""Months of the year."""

NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December")
LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def month_name(month):
    """The English name of `month` (1-12)."""
    if not 1 <= month <= 12:
        raise ValueError("not a month: %r" % month)
    return NAMES[month - 1]


def days_in_month(year, month):
    """The number of days of `month` (1-12) in `year`."""
    if not 1 <= month <= 12:
        raise ValueError("not a month: %r" % month)
    if month == 2 and year % 4 == 0:
        return 29
    return LENGTHS[month - 1]
EOF
cat > 'tests/test_months.py' <<'EOF'
import unittest

from months import days_in_month, month_name


class MonthNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(month_name(1), "January")
        self.assertEqual(month_name(12), "December")
        self.assertRaises(ValueError, month_name, 13)


class DaysInMonthTest(unittest.TestCase):
    def test_lengths(self):
        self.assertEqual(days_in_month(2025, 1), 31)
        self.assertEqual(days_in_month(2025, 4), 30)
        self.assertEqual(days_in_month(2025, 12), 31)

    def test_february(self):
        self.assertEqual(days_in_month(2023, 2), 28)
        self.assertEqual(days_in_month(1900, 2), 29)

    def test_leap_year(self):
        self.assertEqual(days_in_month(2024, 2), 29)
        self.assertEqual(days_in_month(2024, 3), 31)

    def test_not_a_month(self):
        self.assertRaises(ValueError, days_in_month, 2025, 0)
        self.assertRaises(ValueError, days_in_month, 2025, 13)
EOF
rc_commit 20 'P1: review fixes'
rc_publish
