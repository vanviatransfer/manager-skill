#!/usr/bin/env bash
# The workspace of rc-04: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'top' 'Limit option' '`python3 top.py FILE --limit N` prints the N most common words; without the option, ten.' \
  '`top.py`, `README.md`, `tests/`' \
  '`--limit N` prints N words and the default stays 10; `README.md` documents the option and its default'
cat > 'README.md' <<'EOF'
# top

Prints the ten most common words of a text file, most common first:

    python3 top.py FILE
EOF
cat > 'tests/test_top.py' <<'EOF'
import unittest

from top import top_words


class TopWordsTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(top_words("b a B c b a", 2), [("b", 3), ("a", 2)])
EOF
cat > 'top.py' <<'EOF'
"""Prints the ten most common words of a text file: python3 top.py FILE"""
import collections
import sys


def top_words(text, limit=10):
    """The `limit` most common words of `text`, lower-cased, as (word, count) pairs."""
    return collections.Counter(text.lower().split()).most_common(limit)


def main(argv):
    with open(argv[1], encoding="utf-8") as fh:
        for word, count in top_words(fh.read()):
            print(count, word)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
EOF
rc_commit 00 'Base: top'
rc_branch
cat > 'README.md' <<'EOF'
# top

Prints the most common words of a text file, most common first:

    python3 top.py FILE [--limit N]

`--limit N` prints the N most common words (default: 10).
EOF
cat > 'tests/test_top.py' <<'EOF'
import unittest

from top import main, top_words


class TopWordsTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(top_words("b a B c b a", 2), [("b", 3), ("a", 2)])

    def test_limit_option(self):
        import io
        import os
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("b a b c")
            out = io.StringIO()
            with redirect_stdout(out):
                main(["top.py", path, "--limit", "1"])
        self.assertEqual(out.getvalue(), "2 b\n")
EOF
cat > 'top.py' <<'EOF'
"""Prints the most common words of a text file: python3 top.py FILE [--limit N]"""
import argparse
import collections
import sys


def top_words(text, limit=10):
    """The `limit` most common words of `text`, lower-cased, as (word, count) pairs."""
    return collections.Counter(text.lower().split()).most_common(limit)


def main(argv):
    parser = argparse.ArgumentParser(description="Prints the most common words of a file.")
    parser.add_argument("file")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv[1:])
    with open(args.file, encoding="utf-8") as fh:
        for word, count in top_words(fh.read(), args.limit):
            print(count, word)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
EOF
rc_mark_done
rc_commit 10 'P1: Limit option'
rc_publish
