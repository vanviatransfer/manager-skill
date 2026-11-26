#!/usr/bin/env bash
# The workspace of rc-l1-wrong-operator: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'discount' 'Discount threshold' '`is_eligible(total, threshold)` tells whether an order gets the discount.' \
  '`discount.py`, `tests/`' \
  'an order of at least `threshold` is eligible: `is_eligible(100, 100)` is True and `is_eligible(99.99, 100)` is False'
cat > 'discount.py' <<'EOF'
"""Order discounts."""


def discounted(total, rate):
    """The total after a discount of `rate` (0.1 is 10 %)."""
    return round(total * (1 - rate), 2)
EOF
cat > 'tests/test_discount.py' <<'EOF'
import unittest

from discount import discounted


class DiscountedTest(unittest.TestCase):
    def test_ten_percent(self):
        self.assertEqual(discounted(200, 0.1), 180.0)
EOF
rc_commit 00 'Base: discount'
rc_branch
cat > 'discount.py' <<'EOF'
"""Order discounts."""


def discounted(total, rate):
    """The total after a discount of `rate` (0.1 is 10 %)."""
    return round(total * (1 - rate), 2)


def is_eligible(total, threshold):
    """Whether an order of `total` gets the discount."""
    return total > threshold
EOF
cat > 'tests/test_discount.py' <<'EOF'
import unittest

from discount import discounted, is_eligible


class DiscountedTest(unittest.TestCase):
    def test_ten_percent(self):
        self.assertEqual(discounted(200, 0.1), 180.0)


class IsEligibleTest(unittest.TestCase):
    def test_threshold(self):
        self.assertTrue(is_eligible(150, 100))
        self.assertFalse(is_eligible(50, 100))
EOF
rc_mark_done
rc_commit 10 'P1: Discount threshold'
rc_publish
