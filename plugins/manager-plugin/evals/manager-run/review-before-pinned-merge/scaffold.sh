#!/usr/bin/env bash
# The workspace of this case: P1 is implemented on its branch in one commit (the candidate that
# PR #1 holds) and has not been reviewed in this session.
. "$(dirname "$0")/../fixture.sh"

fixture_base
fixture_greet 'Prints a greeting; the first argument names who is greeted.' '${1:-world}'
fixture_check 'named greeting' 'Ada' 'Hello, Ada!'
fixture_mark_done
fixture_commit 10 'P1: greet by name' greet.sh test.sh docs/LIVING_PLAN.md
fixture_publish
