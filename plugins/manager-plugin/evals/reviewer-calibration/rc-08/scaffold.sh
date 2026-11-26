#!/usr/bin/env bash
# The workspace of rc-08: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'ports' 'Port parsing' '`parse_port(text)` reads a TCP port number.' \
  '`ports.py`, `tests/`' \
  'it returns the number for `1` to `65535` and raises ValueError for a non-number and for any number outside 1-65535'
cat > 'ports.py' <<'EOF'
"""Network port helpers."""

WELL_KNOWN = {"http": 80, "https": 443}


def well_known(name):
    """The port of a well-known service name, None for another name."""
    return WELL_KNOWN.get(name)
EOF
cat > 'tests/test_ports.py' <<'EOF'
import unittest

from ports import well_known


class WellKnownTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(well_known("https"), 443)
        self.assertIsNone(well_known("gopher"))
EOF
rc_commit 00 'Base: ports'
rc_branch
cat > 'ports.py' <<'EOF'
"""Network port helpers."""

WELL_KNOWN = {"http": 80, "https": 443}


def well_known(name):
    """The port of a well-known service name, None for another name."""
    return WELL_KNOWN.get(name)


def parse_port(text):
    """The port number in `text`; ValueError when it is not one."""
    port = int(text)
    if not 0 <= port <= 65536:
        raise ValueError("not a port: %s" % text)
    return port
EOF
cat > 'tests/test_ports.py' <<'EOF'
import unittest

from ports import parse_port, well_known


class WellKnownTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(well_known("https"), 443)
        self.assertIsNone(well_known("gopher"))


class ParsePortTest(unittest.TestCase):
    def test_ports(self):
        self.assertEqual(parse_port("1"), 1)
        self.assertEqual(parse_port("8080"), 8080)

    def test_not_a_number(self):
        self.assertRaises(ValueError, parse_port, "http")
EOF
rc_mark_done
rc_commit 10 'P1: Port parsing'
cat > 'ports.py' <<'EOF'
"""Network port helpers."""

WELL_KNOWN = {"http": 80, "https": 443}


def well_known(name):
    """The port of a well-known service name, None for another name."""
    return WELL_KNOWN.get(name)


def parse_port(text):
    """The port number in `text`; ValueError when it is not one."""
    port = int(text)
    if not 0 < port <= 65536:
        raise ValueError("not a port: %s" % text)
    return port
EOF
cat > 'tests/test_ports.py' <<'EOF'
import unittest

from ports import parse_port, well_known


class WellKnownTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(well_known("https"), 443)
        self.assertIsNone(well_known("gopher"))


class ParsePortTest(unittest.TestCase):
    def test_ports(self):
        self.assertEqual(parse_port("1"), 1)
        self.assertEqual(parse_port("8080"), 8080)

    def test_not_a_number(self):
        self.assertRaises(ValueError, parse_port, "http")

    def test_out_of_range(self):
        self.assertRaises(ValueError, parse_port, "0")
EOF
rc_commit 20 'P1: review fixes'
rc_publish
