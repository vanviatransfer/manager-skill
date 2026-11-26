# Shared by the scaffold scripts of the reviewer-calibration cases; sourced, never run.
#
# Builds a tiny synthetic Python project in the current directory (an eval run's working
# directory): project rules, a living plan with one phase P1, a test runner, then whatever the
# case writes. The default branch `main` holds the base commit; the branch `phase/P1` holds the
# candidate (pull request #1). Names, dates and content are fixed, so every commit has the same SHA
# on every machine: the case's prompt names them and `test_reviewer_calibration.py` checks it.
# The answer key (`answer.json` beside the scaffold) never enters the workspace.

set -eu

if [ -e .git ] || [ -e CLAUDE.md ] || [ -e docs ] || [ -e tests ] || [ -e run_tests.py ]; then
  echo "fixture: this directory already holds a repository or a fixture file" >&2
  exit 1
fi

GIT_AUTHOR_NAME='Eval Fixture'
GIT_AUTHOR_EMAIL='fixture@example.invalid'
GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
GIT_DEFAULT_HASH=sha1
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_DEFAULT_HASH

# rc_commit <minute> <message>: commit everything, dated 09:<minute> on the day.
rc_commit() {
  GIT_AUTHOR_DATE="2026-01-05T09:$1:00+00:00"
  GIT_COMMITTER_DATE=$GIT_AUTHOR_DATE
  export GIT_AUTHOR_DATE GIT_COMMITTER_DATE
  git add -A
  git commit -q -m "$2"
}

# rc_base <project> <phase title> <objective> <scope> <acceptance>: the rules, the plan with P1
# still todo and the test runner; the case then writes its code and tests and commits the base.
rc_base() {
  git init -q .
  git symbolic-ref HEAD refs/heads/main
  git config commit.gpgsign false
  git config core.autocrlf false
  mkdir docs tests
  {
    printf '# %s\n\n' "$1"
    printf 'A practice project in standard-library Python 3.\n\n'
    printf -- '- Validation for every change: `python3 run_tests.py` (exit 0).\n'
    printf -- '- One phase per PR, squash merge.\n'
    printf -- '- A practice copy without GitHub: pull request #1 is its branch `phase/P1`, which\n'
    printf '  `origin` (a local mirror) and this checkout already hold.\n'
    printf -- '- No vault and no code map in this project.\n'
  } > CLAUDE.md
  {
    printf '# %s — Living Plan\n\n' "$1"
    printf '## Goal\nThe small library of this repository.\n\n'
    printf '## Constraints and project rules\n'
    printf -- '- Rules: see `CLAUDE.md` (binding for every phase).\n'
    printf -- '- Validation: `python3 run_tests.py`\n\n'
    printf '## Model strategy\n'
    printf 'Model strategy: Sonnet — scope: standing — owner: "Use Sonnet." (2026-01-02)\n\n'
    printf '## Binding decisions\n'
    printf -- '- B1. Standard library only (owner, 2026-01-02)\n\n'
    printf '## Phases\n\n'
    printf 'Status values: `todo` · `in progress (PR #n)` · `done (PR #n)` · `blocked (Dn)`\n'
    printf 'Fix-round limit per phase: 5\n\n'
    printf '### P1. %s\n' "$2"
    printf 'Status: todo\n'
    printf 'Objective: %s\n' "$3"
    printf 'Scope: %s and this phase'"'"'s status line.\n' "$4"
    printf 'Depends on: none\n'
    printf 'Risk: standard — a small change with its tests.\n'
    printf 'Acceptance: %s; tests cover it; `python3 run_tests.py` passes.\n' "$5"
    printf 'Validation: standard\n\n'
    printf '## Change log\n'
    printf -- '- 2026-01-02: plan created.\n'
  } > docs/LIVING_PLAN.md
  cat > run_tests.py <<'EOF'
"""The project's validation: runs tests/test_*.py, exit 0 when every test passed."""
import sys
import unittest

sys.dont_write_bytecode = True
suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
EOF
}

# The phase PR's own plan edit, made with the candidate.
rc_mark_done() {
  sed 's/^Status: todo$/Status: done (PR #1)/' docs/LIVING_PLAN.md > docs/LIVING_PLAN.md.new
  mv docs/LIVING_PLAN.md.new docs/LIVING_PLAN.md
}

# Start the phase branch from the base commit.
rc_branch() {
  git checkout -q -b phase/P1
}

# Both branches go to the mirror; the checkout is left on the candidate, detached and clean.
rc_publish() {
  git init -q --bare .git/fixture-origin.git
  git --git-dir=.git/fixture-origin.git symbolic-ref HEAD refs/heads/main
  git remote add origin "$PWD/.git/fixture-origin.git"
  git push -q origin main phase/P1
  git fetch -q origin
  git remote set-head origin main
  git -c advice.detachedHead=false checkout -q --detach phase/P1
}
