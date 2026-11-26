#!/usr/bin/env bash
# The workspace of rc-31: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'reviews' 'Star ratings' '`stars(rating)` turns an average rating '\
'into the whole number of stars shown.' \
  '`ratings.py`, `tests/`' \
  '`stars(rating)` rounds a rating from 0 to 5 to the nearest whole number '\
'of stars and rounds half up; a rating outside 0-5 raises ValueError'
cat > 'ratings.py' <<'EOF'
"""Ratings of products, 0 to 5."""


def average(ratings):
    """The mean of a list of ratings, None for an empty list."""
    if not ratings:
        return None
    return sum(ratings) / len(ratings)
EOF
cat > 'tests/test_ratings.py' <<'EOF'
import unittest

from ratings import average


class AverageTest(unittest.TestCase):
    def test_average(self):
        self.assertEqual(average([4, 5, 3]), 4)
        self.assertIsNone(average([]))
EOF
rc_commit 00 'Base: reviews'
rc_branch
cat > 'ratings.py' <<'EOF'
"""Ratings of products, 0 to 5."""


def average(ratings):
    """The mean of a list of ratings, None for an empty list."""
    if not ratings:
        return None
    return sum(ratings) / len(ratings)


def stars(rating):
    """The whole number of stars shown for `rating` (0 to 5): the nearest whole number."""
    if not 0 <= rating <= 5:
        raise ValueError("not a rating: %r" % rating)
    return round(rating)
EOF
cat > 'tests/test_ratings.py' <<'EOF'
import unittest

from ratings import average, stars


class AverageTest(unittest.TestCase):
    def test_average(self):
        self.assertEqual(average([4, 5, 3]), 4)
        self.assertIsNone(average([]))


class StarsTest(unittest.TestCase):
    def test_nearest(self):
        self.assertEqual(stars(4.4), 4)
        self.assertEqual(stars(4.6), 5)
        self.assertEqual(stars(0), 0)
        self.assertEqual(stars(5), 5)

    def test_half(self):
        self.assertEqual(stars(3.5), 4)
        self.assertEqual(stars(2.5), 2)

    def test_outside(self):
        self.assertRaises(ValueError, stars, 5.1)
        self.assertRaises(ValueError, stars, -0.5)
EOF
rc_mark_done
rc_commit 10 'P1: Star ratings'
rc_publish
