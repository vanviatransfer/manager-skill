#!/usr/bin/env bash
# The workspace of rc-16: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'roles' 'Permissions' '`permissions(role)` gives the set of actions a role may take.' \
  '`roles.py`, `tests/`' \
  '`viewer` may `read`; `editor` may `read` and `write`; `admin` may `read`, `write` and `delete`; any other role, nothing'
cat > 'roles.py' <<'EOF'
"""Roles and what they may do."""

ROLES = ("admin", "editor", "viewer")


def is_role(name):
    """Whether `name` is one of the roles."""
    return name in ROLES
EOF
cat > 'tests/test_roles.py' <<'EOF'
import unittest

from roles import is_role


class IsRoleTest(unittest.TestCase):
    def test_roles(self):
        self.assertTrue(is_role("editor"))
        self.assertFalse(is_role("owner"))
EOF
rc_commit 00 'Base: roles'
rc_branch
cat > 'roles.py' <<'EOF'
"""Roles and what they may do."""

ROLES = ("admin", "editor", "viewer")


def is_role(name):
    """Whether `name` is one of the roles."""
    return name in ROLES


def permissions(role):
    """The actions `role` may take."""
    granted = set()
    if role == "admin":
        granted.add("delete")
        role = "editor"
    if role == "editor":
        granted.add("write")
        role = "viewer"
    if role == "viewer":
        granted.add("read")
    return granted
EOF
cat > 'tests/test_roles.py' <<'EOF'
import unittest

from roles import is_role, permissions


class IsRoleTest(unittest.TestCase):
    def test_roles(self):
        self.assertTrue(is_role("editor"))
        self.assertFalse(is_role("owner"))


class PermissionsTest(unittest.TestCase):
    def test_each_role(self):
        self.assertEqual(permissions("viewer"), {"read"})
        self.assertEqual(permissions("editor"), {"read", "write"})
        self.assertEqual(permissions("admin"), {"read", "write", "delete"})
        self.assertEqual(permissions("owner"), set())
EOF
rc_mark_done
rc_commit 10 'P1: Permissions'
rc_publish
