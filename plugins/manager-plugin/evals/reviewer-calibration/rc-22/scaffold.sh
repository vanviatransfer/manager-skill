#!/usr/bin/env bash
# The workspace of rc-22: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'settings' 'Settings lookups' '`Settings.get(name, default)` reads '\
'one setting, and a settings file that can'"'"'t be read is logged.' \
  '`settings.py`, `tests/`' \
  '`get` of a missing name returns `default` when one is given (None included) '\
'and raises KeyError when none is; `load` logs a file it can'"'"'t read '\
'or parse with its path and lets the error through'
cat > 'settings.py' <<'EOF'
"""Settings read from a JSON file."""
import json


class Settings:
    def __init__(self, values):
        self._values = dict(values)

    def names(self):
        """The names of the settings, sorted."""
        return sorted(self._values)


def load(path):
    """The settings of the JSON file at `path`."""
    with open(path, encoding="utf-8") as fh:
        return Settings(json.load(fh))
EOF
cat > 'tests/test_settings.py' <<'EOF'
import json
import os
import tempfile
import unittest

from settings import load


class LoadTest(unittest.TestCase):
    def test_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "s.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"b": 2, "a": 1}, fh)
            self.assertEqual(load(path).names(), ["a", "b"])
EOF
rc_commit 00 'Base: settings'
rc_branch
cat > 'settings.py' <<'EOF'
"""Settings read from a JSON file."""
import json
import logging

log = logging.getLogger(__name__)
_NO_DEFAULT = object()


class Settings:
    def __init__(self, values):
        self._values = dict(values)

    def names(self):
        """The names of the settings, sorted."""
        return sorted(self._values)

    def get(self, name, default=_NO_DEFAULT):
        """The value of setting `name`; `default` when there is none, KeyError without one."""
        try:
            return self._values[name]
        except KeyError:
            if default is _NO_DEFAULT:
                raise
            return default


def load(path):
    """The settings of the JSON file at `path`."""
    try:
        with open(path, encoding="utf-8") as fh:
            return Settings(json.load(fh))
    except Exception:
        log.exception("can't read the settings file %s", path)
        raise
EOF
cat > 'tests/test_settings.py' <<'EOF'
import json
import os
import tempfile
import unittest

from settings import Settings, load


class LoadTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "s.json")

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_load(self):
        self.write(json.dumps({"b": 2, "a": 1}))
        self.assertEqual(load(self.path).names(), ["a", "b"])

    def test_a_bad_file_is_logged_and_raised(self):
        self.write("{not json")
        with self.assertLogs("settings", "ERROR") as logs:
            self.assertRaises(ValueError, load, self.path)
        self.assertIn(self.path, logs.output[0])

    def test_a_missing_file_is_logged_and_raised(self):
        with self.assertLogs("settings", "ERROR"):
            self.assertRaises(FileNotFoundError, load, self.path)


class GetTest(unittest.TestCase):
    def test_get(self):
        settings = Settings({"a": 1, "b": None})
        self.assertEqual(settings.get("a"), 1)
        self.assertIsNone(settings.get("b", 5))
        self.assertEqual(settings.get("c", 5), 5)
        self.assertIsNone(settings.get("c", None))
        self.assertRaises(KeyError, settings.get, "c")
EOF
rc_mark_done
rc_commit 10 'P1: Settings lookups'
rc_publish
