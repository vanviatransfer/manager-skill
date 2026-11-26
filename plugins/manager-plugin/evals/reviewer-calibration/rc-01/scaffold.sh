#!/usr/bin/env bash
# The workspace of rc-01: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'visits' 'Strict lookups' '`Store.find` raises `KeyError` for a missing key instead of returning None, so a stored None is told apart from a missing key.' \
  '`store.py`, `service.py`, `tests/`' \
  '`find` of a missing key raises KeyError; `find` of a key stored with the value None returns None; the store'"'"'s users keep their behaviour'
cat > 'service.py' <<'EOF'
"""Counts visits per page."""
from store import Store

visits = Store()


def record(page):
    """Counts one visit of `page` and returns the page's count so far."""
    count = visits.find(page)
    if count is None:
        count = 0
    visits.put(page, count + 1)
    return count + 1
EOF
cat > 'store.py' <<'EOF'
"""An in-memory key-value store."""


class Store:
    def __init__(self):
        self._items = {}

    def put(self, key, value):
        self._items[key] = value

    def find(self, key):
        """The value stored under `key`, None when there is none."""
        return self._items.get(key)
EOF
cat > 'tests/test_store.py' <<'EOF'
import unittest

from store import Store


class StoreTest(unittest.TestCase):
    def test_put_and_find(self):
        store = Store()
        store.put("a", 1)
        self.assertEqual(store.find("a"), 1)
EOF
rc_commit 00 'Base: visits'
rc_branch
cat > 'store.py' <<'EOF'
"""An in-memory key-value store."""


class Store:
    def __init__(self):
        self._items = {}

    def put(self, key, value):
        self._items[key] = value

    def find(self, key):
        """The value stored under `key`; KeyError when there is none."""
        return self._items[key]
EOF
cat > 'tests/test_store.py' <<'EOF'
import unittest

from store import Store


class StoreTest(unittest.TestCase):
    def test_put_and_find(self):
        store = Store()
        store.put("a", 1)
        self.assertEqual(store.find("a"), 1)

    def test_missing_key(self):
        self.assertRaises(KeyError, Store().find, "a")

    def test_stored_none(self):
        store = Store()
        store.put("a", None)
        self.assertIsNone(store.find("a"))
EOF
rc_mark_done
rc_commit 10 'P1: Strict lookups'
rc_publish
