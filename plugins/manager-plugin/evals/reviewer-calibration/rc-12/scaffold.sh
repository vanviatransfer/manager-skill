#!/usr/bin/env bash
# The workspace of rc-12: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'args' 'Split at --' '`split_args(args)` splits a list of arguments at the first `--`.' \
  '`args.py`, `tests/`' \
  'it returns the arguments before the first `--` and those after it, the `--` itself in neither; without a `--`, all of them and an empty list'
cat > 'args.py' <<'EOF'
"""Command-line argument helpers."""


def is_flag(arg):
    """Whether `arg` is a flag: it starts with a dash and is not a lone dash."""
    return arg.startswith("-") and arg != "-"
EOF
cat > 'tests/test_args.py' <<'EOF'
import unittest

from args import is_flag


class IsFlagTest(unittest.TestCase):
    def test_flags(self):
        self.assertTrue(is_flag("-v"))
        self.assertFalse(is_flag("-"))
        self.assertFalse(is_flag("file"))
EOF
rc_commit 00 'Base: args'
rc_branch
cat > 'args.py' <<'EOF'
"""Command-line argument helpers."""


def is_flag(arg):
    """Whether `arg` is a flag: it starts with a dash and is not a lone dash."""
    return arg.startswith("-") and arg != "-"


def split_args(args):
    """The arguments before the first "--" and those after it."""
    before = []
    for index, arg in enumerate(args):
        if arg == "--":
            after = args[index + 1:]
            break
        before.append(arg)
    else:
        after = []
    return before, after
EOF
cat > 'tests/test_args.py' <<'EOF'
import unittest

from args import is_flag, split_args


class IsFlagTest(unittest.TestCase):
    def test_flags(self):
        self.assertTrue(is_flag("-v"))
        self.assertFalse(is_flag("-"))
        self.assertFalse(is_flag("file"))


class SplitArgsTest(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split_args(["-a", "--", "-b"]), (["-a"], ["-b"]))
        self.assertEqual(split_args(["--", "--"]), ([], ["--"]))

    def test_without_a_separator(self):
        self.assertEqual(split_args(["-a"]), (["-a"], []))
        self.assertEqual(split_args([]), ([], []))
EOF
rc_mark_done
rc_commit 10 'P1: Split at --'
rc_publish
