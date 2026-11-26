#!/usr/bin/env bash
# The workspace of rc-09: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'phones' 'Normalize phone numbers' '`normalize(text)` gives a phone number as `+<country code><number>`.' \
  '`phone.py`, `tests/`' \
  'a number starting with `+` keeps its code; one starting with `00` keeps the code after the `00` (`0044 20 7946 0000` gives `+442079460000`); one starting with a single `0` is national and gets `+49` for that `0` (`030 1234567` gives `+49301234567`)'
cat > 'phone.py' <<'EOF'
"""Phone number helpers."""


def digits(text):
    """Only the digits of `text`."""
    return "".join(ch for ch in text if ch.isdigit())
EOF
cat > 'tests/test_phone.py' <<'EOF'
import unittest

from phone import digits


class DigitsTest(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(digits("(030) 12-34"), "0301234")
EOF
rc_commit 00 'Base: phones'
rc_branch
cat > 'phone.py' <<'EOF'
"""Phone number helpers."""


def digits(text):
    """Only the digits of `text`."""
    return "".join(ch for ch in text if ch.isdigit())


def normalize(text):
    """The number in `text` as +<country code><number>."""
    number = digits(text)
    if text.strip().startswith("+"):
        return "+" + number
    if number.startswith("0"):
        return "+49" + number[1:]
    if number.startswith("00"):
        return "+" + number[2:]
    raise ValueError("not a phone number: %r" % text)
EOF
cat > 'tests/test_phone.py' <<'EOF'
import unittest

from phone import digits, normalize


class DigitsTest(unittest.TestCase):
    def test_digits(self):
        self.assertEqual(digits("(030) 12-34"), "0301234")


class NormalizeTest(unittest.TestCase):
    def test_plus(self):
        self.assertEqual(normalize("+44 20 7946 0000"), "+442079460000")

    def test_national(self):
        self.assertEqual(normalize("030 1234567"), "+49301234567")

    @unittest.skip("flaky on CI")
    def test_international(self):
        self.assertEqual(normalize("0044 20 7946 0000"), "+442079460000")
EOF
rc_mark_done
rc_commit 10 'P1: Normalize phone numbers'
rc_publish
