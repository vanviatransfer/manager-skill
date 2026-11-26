#!/usr/bin/env bash
# The workspace of rc-clean-retry: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'retry' 'Retry decision' '`should_retry(status, attempt, max_attempts)` tells whether to try again after attempt number `attempt` (1-based) failed with HTTP `status`.' \
  '`retry.py`, `tests/`' \
  'only the statuses in `RETRYABLE` are retried; never more than `max_attempts` attempts in total, whatever the status'
cat > 'retry.py' <<'EOF'
"""When to retry a failed request."""

RETRYABLE = (429, 500, 502, 503, 504)


def delay(attempt):
    """Seconds to wait before attempt `attempt` (1-based): 1, 2, 4, ..."""
    return 2 ** (attempt - 1)
EOF
cat > 'tests/test_retry.py' <<'EOF'
import unittest

from retry import delay


class DelayTest(unittest.TestCase):
    def test_doubles(self):
        self.assertEqual([delay(n) for n in (1, 2, 3)], [1, 2, 4])
EOF
rc_commit 00 'Base: retry'
rc_branch
cat > 'retry.py' <<'EOF'
"""When to retry a failed request."""

RETRYABLE = (429, 500, 502, 503, 504)


def delay(attempt):
    """Seconds to wait before attempt `attempt` (1-based): 1, 2, 4, ..."""
    return 2 ** (attempt - 1)


def should_retry(status, attempt, max_attempts):
    """Whether to try again after attempt `attempt` failed with `status`."""
    return status in RETRYABLE and attempt < max_attempts
EOF
cat > 'tests/test_retry.py' <<'EOF'
import unittest

from retry import delay, should_retry


class DelayTest(unittest.TestCase):
    def test_doubles(self):
        self.assertEqual([delay(n) for n in (1, 2, 3)], [1, 2, 4])


class ShouldRetryTest(unittest.TestCase):
    def test_server_errors_until_the_limit(self):
        self.assertTrue(should_retry(503, 1, 3))
        self.assertFalse(should_retry(503, 3, 3))

    def test_rate_limit(self):
        self.assertTrue(should_retry(429, 1, 3))

    def test_client_error(self):
        self.assertFalse(should_retry(404, 1, 3))

    def test_rate_limit_stops_at_the_limit(self):
        self.assertFalse(should_retry(429, 3, 3))
EOF
rc_mark_done
rc_commit 10 'P1: Retry decision'
rc_publish
