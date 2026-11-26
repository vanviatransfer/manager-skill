#!/usr/bin/env bash
# The workspace of rc-27: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'service' 'Port setting' '`load` also reads the `port` setting, '\
'8080 when the document has none.' \
  '`config.py`, `tests/`' \
  '`load` of a document with a `port` gives that port in its result, of '\
'one without a `port` gives 8080'
sed 's/^- B1\. Standard library only (owner, 2026-01-02)$/&\
- B2. `config.load` never raises; on bad input it returns None (owner, 2026-01-02)/' \
  docs/LIVING_PLAN.md > docs/LIVING_PLAN.md.new
mv docs/LIVING_PLAN.md.new docs/LIVING_PLAN.md
cat > 'config.py' <<'EOF'
"""The service's configuration, a JSON document."""
import json


def load(text):
    """The configuration in the JSON document `text`, None when it is not a valid one."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("host"), str):
        return None
    return {"host": data["host"]}
EOF
cat > 'tests/test_config.py' <<'EOF'
import unittest

from config import load


class LoadTest(unittest.TestCase):
    def test_load(self):
        self.assertEqual(load('{"host": "example.org"}'), {"host": "example.org"})

    def test_bad_input(self):
        for text in ("{", "[]", "{}", '{"host": 1}'):
            with self.subTest(text=text):
                self.assertIsNone(load(text))
EOF
rc_commit 00 'Base: service'
rc_branch
cat > 'config.py' <<'EOF'
"""The service's configuration, a JSON document."""
import json

DEFAULT_PORT = 8080


def load(text):
    """The configuration in the JSON document `text`, None when it is not a valid one."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("host"), str):
        return None
    return {"host": data["host"], "port": int(data.get("port", DEFAULT_PORT))}
EOF
cat > 'tests/test_config.py' <<'EOF'
import unittest

from config import load


class LoadTest(unittest.TestCase):
    def test_load(self):
        self.assertEqual(load('{"host": "example.org"}'), {"host": "example.org", "port": 8080})

    def test_port(self):
        self.assertEqual(load('{"host": "example.org", "port": 9000}')["port"], 9000)
        self.assertEqual(load('{"host": "example.org", "port": "9000"}')["port"], 9000)

    def test_bad_input(self):
        for text in ("{", "[]", "{}", '{"host": 1}'):
            with self.subTest(text=text):
                self.assertIsNone(load(text))
EOF
rc_mark_done
rc_commit 10 'P1: Port setting'
rc_publish
