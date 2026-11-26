#!/usr/bin/env bash
# The workspace of rc-30: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'sequences' 'Fibonacci numbers' '`fibonacci(n)` gives the n-th Fibonacci '\
'number, without computing the earlier ones again on every call.' \
  '`sequences.py`, `tests/`' \
  '`fibonacci(n)` gives the n-th Fibonacci number (`fibonacci(0)` is 0, '\
'`fibonacci(1)` is 1) for any n >= 0 and raises ValueError for a negative '\
'n; a call reuses the numbers that earlier calls computed'
cat > 'sequences.py' <<'EOF'
"""Integer sequences."""


def triangular(n):
    """The n-th triangular number, 0 + 1 + ... + n, for n >= 0."""
    if n < 0:
        raise ValueError("n must be at least 0")
    return n * (n + 1) // 2
EOF
cat > 'tests/test_sequences.py' <<'EOF'
import unittest

from sequences import triangular


class TriangularTest(unittest.TestCase):
    def test_triangular(self):
        self.assertEqual([triangular(n) for n in range(5)], [0, 1, 3, 6, 10])
        self.assertRaises(ValueError, triangular, -1)
EOF
rc_commit 00 'Base: sequences'
rc_branch
cat > 'sequences.py' <<'EOF'
"""Integer sequences."""


def triangular(n):
    """The n-th triangular number, 0 + 1 + ... + n, for n >= 0."""
    if n < 0:
        raise ValueError("n must be at least 0")
    return n * (n + 1) // 2


def fibonacci(n, _known=[0, 1]):
    """The n-th Fibonacci number, for n >= 0. `_known` is not a parameter for callers: its
    default list is shared by every call on purpose and holds the numbers found so far, so a
    call computes only the ones past the highest an earlier call reached."""
    if n < 0:
        raise ValueError("n must be at least 0")
    while len(_known) <= n:
        _known.append(_known[-1] + _known[-2])
    return _known[n]
EOF
cat > 'tests/test_sequences.py' <<'EOF'
import unittest

from sequences import fibonacci, triangular


class TriangularTest(unittest.TestCase):
    def test_triangular(self):
        self.assertEqual([triangular(n) for n in range(5)], [0, 1, 3, 6, 10])
        self.assertRaises(ValueError, triangular, -1)


class FibonacciTest(unittest.TestCase):
    def test_first_numbers(self):
        self.assertEqual([fibonacci(n) for n in range(10)], [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_any_order(self):
        self.assertEqual(fibonacci(90), 2880067194370816120)
        self.assertEqual(fibonacci(12), 144)
        self.assertEqual(fibonacci(91), 4660046610375530309)
        self.assertEqual(fibonacci(0), 0)

    def test_the_numbers_are_kept(self):
        fibonacci(30)
        known = fibonacci.__defaults__[0]
        self.assertGreaterEqual(len(known), 31)
        self.assertEqual(known[:6], [0, 1, 1, 2, 3, 5])

    def test_negative(self):
        self.assertRaises(ValueError, fibonacci, -1)
EOF
rc_mark_done
rc_commit 10 'P1: Fibonacci numbers'
rc_publish
