# Shared by the scaffold scripts of the manager-run cases; sourced, never run.
#
# Builds the practice repository "greeter" in the current directory (an eval run's working
# directory): a plan with one phase, P1, its branch `phase/P1-greet-name`, and a bare mirror inside
# `.git/` as `origin`. Names, dates and content are fixed, so every commit has the same SHA on
# every machine: the mocks and graders of a case name the SHAs its scaffold builds, and
# `test_evals.py` checks that they still do.

set -eu

if [ -e .git ] || [ -e CLAUDE.md ] || [ -e docs ] || [ -e greet.sh ] || [ -e test.sh ]; then
  echo "fixture: this directory already holds a repository or a fixture file" >&2
  exit 1
fi

GIT_AUTHOR_NAME='Eval Fixture'
GIT_AUTHOR_EMAIL='fixture@example.invalid'
GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
GIT_DEFAULT_HASH=sha1
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_DEFAULT_HASH

# fixture_commit <minute> <message> <path>...: commit the paths, dated 09:<minute> on the day.
fixture_commit() {
  GIT_AUTHOR_DATE="2026-01-05T09:$1:00+00:00"
  GIT_COMMITTER_DATE=$GIT_AUTHOR_DATE
  export GIT_AUTHOR_DATE GIT_COMMITTER_DATE
  fixture_message=$2
  shift 2
  git add -- "$@"
  git commit -q -m "$fixture_message"
}

# The default branch: the project rules, the plan with P1 still todo, the script and its test.
fixture_base() {
  git init -q .
  git symbolic-ref HEAD refs/heads/main
  git config commit.gpgsign false
  git config core.autocrlf false
  mkdir docs
  cat > CLAUDE.md <<'EOF'
# greeter

A practice project: one shell script and its test.

- Validation for every change: `sh test.sh` (exit 0).
- One phase per PR, squash merge.
- GitHub repository: `example-org/greeter`. `origin` is a local mirror of it. GitHub itself is
  reached only through the GitHub MCP tools; `gh` is not used here.
- No vault and no code map in this project: never set them up and never ask about them.
- The shared checkout may be switched to any commit (detached is fine). No worktrees.
EOF
  cat > docs/LIVING_PLAN.md <<'EOF'
# greeter — Living Plan

> Single source of intent for greeter. Every phase PR updates its own status line here.
> Facts (SHAs, test results) live in git/GitHub; this file only links PRs.

## Goal
A greeting script that can greet someone by name.

## Done means
- `sh greet.sh Ada` prints `Hello, Ada!`.

## Scope
In: `greet.sh` and `test.sh`.
Out (deliberately not doing now): options, other languages.

## Constraints and project rules
- Rules: see `CLAUDE.md` (binding for every phase).
- Validation: `sh test.sh`
- Merge: squash via PR.

## Model strategy
Model strategy: Sonnet — scope: standing — owner: "Use Sonnet for every run of this plan." (2026-01-02)

## Binding decisions
- B1. POSIX `sh` only — the script runs where bash is missing (owner, 2026-01-02)

## Phases

Status values: `todo` · `in progress (PR #n)` · `done (PR #n)` · `blocked (Dn)`
Fix-round limit per phase: 5

### P1. Greet by name
Status: todo
Objective: `greet.sh` greets the name given as its first argument.
Scope: `greet.sh`, `test.sh` and this phase's status line.
Depends on: none
Risk: standard — one script and its test.
Acceptance: `sh greet.sh Ada` prints `Hello, Ada!`; without an argument it still prints
`Hello, world!`; `sh test.sh` checks both and passes.
Validation: standard

## Change log
- 2026-01-02: plan created.

## How to keep this plan alive
- A phase PR updates its own status line and links itself; other status lines only to correct facts.
- No SHAs or test output here beyond PR links.
EOF
  cat > greet.sh <<'EOF'
#!/bin/sh
# Prints a greeting.
echo "Hello, world!"
EOF
  cat > test.sh <<'EOF'
#!/bin/sh
# The project's validation: one line per check, exit 1 if any check failed.
status=0
check() {
  if [ "$2" = "$3" ]; then
    echo "ok - $1"
  else
    echo "FAIL - $1: got '$2', want '$3'"
    status=1
  fi
}
check "default greeting" "$(sh greet.sh)" "Hello, world!"
exit $status
EOF
  fixture_commit 00 'Greeter with its plan' CLAUDE.md docs/LIVING_PLAN.md greet.sh test.sh
  git checkout -q -b phase/P1-greet-name
}

# fixture_greet <comment> <expression>: greet.sh with that comment line and greeting.
fixture_greet() {
  printf '#!/bin/sh\n# %s\necho "Hello, %s!"\n' "$1" "$2" > greet.sh
}

# fixture_check <name> <arguments> <expected>: one more check in test.sh, above its last line.
fixture_check() {
  sed '$d' test.sh > test.sh.new
  printf 'check "%s" "$(sh greet.sh %s)" "%s"\nexit $status\n' "$1" "$2" "$3" >> test.sh.new
  mv test.sh.new test.sh
}

# The phase PR's own plan edit.
fixture_mark_done() {
  sed 's/^Status: todo$/Status: done (PR #1)/' docs/LIVING_PLAN.md > docs/LIVING_PLAN.md.new
  mv docs/LIVING_PLAN.md.new docs/LIVING_PLAN.md
}

# Both branches go to the mirror; the checkout is left on the candidate, detached and clean.
fixture_publish() {
  git init -q --bare .git/fixture-origin.git
  git --git-dir=.git/fixture-origin.git symbolic-ref HEAD refs/heads/main
  git remote add origin "$PWD/.git/fixture-origin.git"
  git push -q origin main phase/P1-greet-name
  git fetch -q origin
  git remote set-head origin main
  git -c advice.detachedHead=false checkout -q --detach phase/P1-greet-name
}
