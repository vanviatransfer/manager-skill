#!/usr/bin/env bash
# The workspace of rc-32: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'records' 'Field limits' '`over_limit(record, limits)` names the '\
'fields of a record above their maximum, through one check per field.' \
  '`limits.py`, `tests/`' \
  '`limit_checks(limits)` gives one check per field of `limits` ({field: '\
'maximum}), True when a value is at most that field'"'"'s maximum; `over_limit(record, '\
'limits)` gives the sorted fields of `record` above their maximum'
cat > 'limits.py' <<'EOF'
"""Limits on the fields of records."""


def parse_limits(text):
    """{field: maximum} from lines "field = maximum"; blank lines are skipped."""
    limits = {}
    for line in text.splitlines():
        if line.strip():
            field, maximum = line.split("=")
            limits[field.strip()] = float(maximum)
    return limits
EOF
cat > 'tests/test_limits.py' <<'EOF'
import unittest

from limits import parse_limits


class ParseLimitsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_limits("age = 120\n\nweight=300.5\n"),
                         {"age": 120.0, "weight": 300.5})
EOF
rc_commit 00 'Base: records'
rc_branch
cat > 'limits.py' <<'EOF'
"""Limits on the fields of records."""


def parse_limits(text):
    """{field: maximum} from lines "field = maximum"; blank lines are skipped."""
    limits = {}
    for line in text.splitlines():
        if line.strip():
            field, maximum = line.split("=")
            limits[field.strip()] = float(maximum)
    return limits


def limit_checks(limits):
    """{field: check} for `limits` ({field: maximum}); check(value) is True when `value` is at
    most the field's maximum."""
    checks = {}
    for field, maximum in limits.items():
        checks[field] = lambda value: value <= maximum
    return checks


def over_limit(record, limits):
    """The fields of `record` whose value is above their maximum in `limits`, sorted; fields
    without a limit are not checked."""
    checks = limit_checks(limits)
    return sorted(field for field, value in record.items()
                  if field in checks and not checks[field](value))
EOF
cat > 'tests/test_limits.py' <<'EOF'
import unittest

from limits import limit_checks, over_limit, parse_limits


class ParseLimitsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_limits("age = 120\n\nweight=300.5\n"),
                         {"age": 120.0, "weight": 300.5})


class LimitChecksTest(unittest.TestCase):
    def test_check(self):
        check = limit_checks({"age": 120})["age"]
        self.assertTrue(check(30))
        self.assertTrue(check(120))
        self.assertFalse(check(121))
        self.assertEqual(limit_checks({}), {})


class OverLimitTest(unittest.TestCase):
    def test_over_limit(self):
        self.assertEqual(over_limit({"age": 130, "name": "x"}, {"age": 120}), ["age"])
        self.assertEqual(over_limit({"age": 20}, {"age": 120}), [])
EOF
rc_mark_done
rc_commit 10 'P1: Field limits'
rc_publish
