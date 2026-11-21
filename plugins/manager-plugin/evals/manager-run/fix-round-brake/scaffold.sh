#!/usr/bin/env bash
# The workspace of this case: P1's branch after five fix rounds. Each commit below is the
# candidate one earlier review refused (the ledger in mocks/ names them in this order); the last
# one, the fifth fix, breaks the default greeting, so `sh test.sh` fails at the candidate.
. "$(dirname "$0")/../fixture.sh"

fixture_base
fixture_greet 'Prints a greeting.' '${1:-world}'
fixture_commit 10 'P1: greet by name' greet.sh
fixture_check 'named greeting' 'Ada' 'Hello, Ada!'
fixture_commit 20 'P1: test the named greeting' test.sh
fixture_mark_done
fixture_commit 30 'P1: mark the phase done in the plan' docs/LIVING_PLAN.md
fixture_check 'name with a space' '"Ada Lovelace"' 'Hello, Ada Lovelace!'
fixture_commit 40 'P1: test a name with a space' test.sh
fixture_greet 'Prints a greeting; the first argument names who is greeted.' '${1:-world}'
fixture_commit 50 'P1: say what the argument is' greet.sh
fixture_greet 'Prints a greeting; the arguments name who is greeted.' '$*'
fixture_commit 55 'P1: greet every argument' greet.sh
fixture_publish
