#!/usr/bin/env bash
# The workspace of rc-decoy-ceil-idiom: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'jobs' 'Batch count' '`batch_count(n, size)` gives the number of batches `batch` makes of `n` items, without building them.' \
  '`jobs.py`, `tests/`' \
  '`batch_count(n, size)` equals `len(batch(list(range(n)), size))` for every `n` of 0 or more and `size` of 1 or more'
cat > 'jobs.py' <<'EOF'
"""Splits work into batches."""


def batch(items, size):
    """The items in lists of `size`, the last one shorter."""
    return [items[i:i + size] for i in range(0, len(items), size)]
EOF
cat > 'tests/test_jobs.py' <<'EOF'
import unittest

from jobs import batch


class BatchTest(unittest.TestCase):
    def test_batches(self):
        self.assertEqual(batch([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
EOF
rc_commit 00 'Base: jobs'
rc_branch
cat > 'jobs.py' <<'EOF'
"""Splits work into batches."""


def batch(items, size):
    """The items in lists of `size`, the last one shorter."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def batch_count(n, size):
    """How many batches `batch` makes of `n` items."""
    return -(-n // size)
EOF
cat > 'tests/test_jobs.py' <<'EOF'
import unittest

from jobs import batch, batch_count


class BatchTest(unittest.TestCase):
    def test_batches(self):
        self.assertEqual(batch([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])


class BatchCountTest(unittest.TestCase):
    def test_matches_batch(self):
        for n in range(12):
            for size in (1, 2, 5):
                self.assertEqual(batch_count(n, size), len(batch(list(range(n)), size)))
EOF
rc_mark_done
rc_commit 10 'P1: Batch count'
rc_publish
