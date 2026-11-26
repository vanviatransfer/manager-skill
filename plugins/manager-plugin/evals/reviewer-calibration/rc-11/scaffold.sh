#!/usr/bin/env bash
# The workspace of rc-11: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'settings' 'Layered settings' '`config.load(paths)` reads several JSON settings files and merges them, a later file winning.' \
  '`config.py`, `cli.py`, `tests/`' \
  '`load([a, b])` returns the settings of `a` updated by those of `b`; `python3 cli.py SETTINGS.json` still prints the configured name'
cat > 'cli.py' <<'EOF'
"""Prints the configured name: python3 cli.py SETTINGS.json"""
import sys

import config


def main(argv):
    settings = config.load(argv[1])
    print(settings.get("name", "unnamed"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
EOF
cat > 'config.py' <<'EOF'
"""Reads the settings file."""
import json


def load(path):
    """The settings in the JSON file at `path`, as a dict."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
EOF
cat > 'tests/test_config.py' <<'EOF'
import json
import os
import tempfile
import unittest

import config


class LoadTest(unittest.TestCase):
    def write(self, folder, name, settings):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh)
        return path

    def test_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "a.json", {"name": "a"})
            self.assertEqual(config.load(path), {"name": "a"})
EOF
rc_commit 00 'Base: settings'
rc_branch
cat > 'config.py' <<'EOF'
"""Reads the settings files."""
import json


def load(paths):
    """The settings of the JSON files at `paths`, merged in order: a later file wins."""
    settings = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            settings.update(json.load(fh))
    return settings
EOF
cat > 'tests/test_config.py' <<'EOF'
import json
import os
import tempfile
import unittest

import config


class LoadTest(unittest.TestCase):
    def write(self, folder, name, settings):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh)
        return path

    def test_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "a.json", {"name": "a"})
            self.assertEqual(config.load([path]), {"name": "a"})

    def test_a_later_file_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            a = self.write(folder, "a.json", {"name": "a", "x": 1})
            b = self.write(folder, "b.json", {"name": "b"})
            self.assertEqual(config.load([a, b]), {"name": "b", "x": 1})
EOF
rc_mark_done
rc_commit 10 'P1: Layered settings'
rc_publish
