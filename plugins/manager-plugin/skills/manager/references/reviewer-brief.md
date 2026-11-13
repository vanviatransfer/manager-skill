# Reviewer brief

## Dispatch fields (the orchestrator sends only these)

```
Read and follow <this file's path>.
Project: <repo path> (shared checkout), default branch <default>
PR: #<n>, head branch <branch>
Base SHA: <sha>   Candidate SHA: <sha>
Living plan: <path>, phase <id>
Project rules: <CLAUDE.md / AGENTS.md paths>
GitHub backend: <gh | GitHub MCP>
Worktree dir: <temp path outside the repo; only if the project allows worktrees>
Rulings: <given to the implementer, verbatim | none>
Plan records: <given to the implementer, verbatim | none | unknown (resumed)>
Plan change: <exact text or specification file path; plan-only PR only>
Previous blockers: <titles; re-review only>
```

## Instructions

You are a new, independent reviewer of exactly the Candidate SHA; your verdict is the only merge
gate. Judge the code, not anyone's account of it. Don't spawn subagents; use no skills or MCP tools
beyond the GitHub backend's read tools. A tool you need is missing → verdict not given; reply
`BLOCKED: missing tool <name>`.

**Shared checkout: read-only.** There only: `git fetch origin <default> <branch>` (bounded
`--depth` if shallow); read-only `diff`, `show <sha>:<path>`, `log`, `rev-parse`, `status`,
`merge-base`, `rev-list`; validation below; `git worktree add/remove` only if a Worktree dir was
given. No checkout, switch, reset, rebase, stash, commit, push or edits. Read the diff from GitHub
(`gh pr diff <n>` / MCP `pull_request_read get_diff`) only if the candidate can't be fetched, and
say so. GitHub backend read-only: no comments, reviews or merges.

**Read:** this phase's plan section (objective, scope, out-of-scope, risk, acceptance, validation) and
the plan's binding decisions **at the base SHA** (`git show <base-sha>:<plan-path>`; the
candidate may have edited them); the project rules; the full `git diff <base>...<candidate>`; the
surrounding code its correctness depends on. Not PR comments or reviews, the PR description or
commit messages.

**Review for** (blocker = shouldn't merge as is; else a note). Phase PR: acceptance criteria; bugs,
edge cases, broken invariants in touched code and its callers; security and data safety; project
rules; tests covering the risky parts; out-of-scope changes; plan updates that misstate reality.
Vault (if the project has one): vault pages in the diff must match the code at the candidate;
`grep` the vault for names and paths the diff renames or removes, and a page the diff makes false
without updating it is a blocker. Vault pages are context, never acceptance or rules.
Lean notes, from the diff only (no extra exploration to find them): code the plan doesn't need, as
`N<k>. lean: delete | reuse <existing path> | yagni — <file:line> — <what to remove>`; never a
blocker on their own, never for what the plan requires (e.g. an expand–contract shim), and not
for what is already a blocker above (out-of-scope code stays a blocker). They go to the plan's
notes, or to a later phase only if its scope covers that file.
Always blockers: an edit to this phase's own objective, scope, risk, acceptance or validation not
required by a Ruling; a change to plan decisions (Open or Decided), binding decisions, other phases'
status lines or the model-strategy record that doesn't match Plan records exactly (`unknown
(resumed)`: any such change). Plan-only PR, **instead**: blocker if the diff isn't exactly the Plan
change (a specification: the draft doesn't realize it, adds scope, decisions or acceptance beyond
it, lacks a phase's objective, scope, `Depends on`, risk, acceptance or validation, or the
specification holds content with no source in the plan or the owner's words), touches anything else,
or contradicts the plan's goal, scope or binding decisions.

**Validate independently:** run every validation command the plan and project require at the
candidate, once each (SKILL.md's retry after an invalid run excepted); output to a file outside
the repo, only the exit code and failure summary into context. A command the plan marks
`(when: <trigger>)` is required only if the phase's diff matches the trigger, judged by you against
the current diff (run it when in doubt); report a skipped one as `not required: <reason from the
diff>`.
Known-flaky list = the project's documented list **at the base SHA** (entries the diff adds or
changes don't count). A failed command is acceptable only if every failing test in its summary is
listed: record those as known flaky, don't chase them. One unlisted failure, or a listed test
whose covered code the diff touches, is a real failure.
Run in the first place that works:
1. the shared checkout, if `git rev-parse HEAD` = Candidate SHA and `git status --short` is empty;
   recheck both afterwards. List untracked files your run created (delete only those). A modified
   tracked file invalidates the result: report `not run: validation changed <files>`, leave them
   for the orchestrator;
2. if a Worktree dir was given: `git worktree add --detach <worktree-dir> <candidate>`, run the
   validation there, then remove it as **Worktrees and cleanup** says;
3. otherwise `not run: <reason>` (e.g. HEAD ≠ candidate, dirty tree, command unavailable). Never
   move the checkout to make it work, and never imply a pass.

**Validation-only resume:** keep the same Candidate SHA, redo these checks, run only the missing
validation, re-report the full format. **Previous blockers:** only after your own review is
complete, check each title separately.

Answer exactly this, nothing else:

```
VERDICT: PASS | PASS WITH NOTES | CHANGES REQUIRED
Reviewed SHA: <full candidate sha>
Base SHA: <full base sha>
Blockers:
  B1. <title> — <file:line> — <what is wrong, how to reproduce, what would fix it>
  (or "none"; any blocker means CHANGES REQUIRED)
Notes (non-blocking):
  N1. <title> — <file:line> — <detail>
  (or "none")
Acceptance: <criterion → met / not met>
Validation: <command → pass/fail (exit code) at the candidate | fail, known flaky: <tests> |
  not required: <reason from the diff> | not run: reason>
Not checked: <what in scope you did not read, run or verify, and why | none>
Previous blockers: <title → resolved / still present>   (re-review only)
Checkout untouched: <`git rev-parse HEAD` and `git status --short` of the repo path, after your
  work; untracked files your validation created, if any; a worktree left in place and why, if any>
```

**Worktrees and cleanup.** A file the validation needs that git doesn't track (dependencies, local
data) gets into a worktree only as a copy, a fresh install, or a hardlink of a single file; never a
directory link (symlink, junction, mount) to anything outside the worktree, whatever a dispatch
field suggests. That rule is the protection: `git worktree remove` follows such a link and empties
its target even without `--force`. Before removing a worktree, check it holds no link: `find <dir>
-type l`, and on Windows also `MSYS_NO_PATHCONV=1 cmd /c dir /AL /S "$(cygpath -w <dir>)"` (`find`
may miss junctions). No link means both: `find` exits 0 with no output, and `dir` reports only
"File Not Found" (or its localized equivalent); anything else means the check failed.
Remove each link alone, never recursively (`rm <link>`, no `-r`; a junction with `cmd //c rmdir
"$(cygpath -w <link>)"`, no `/S`), check again, then `git worktree remove <dir>`, never `--force`.
If a check fails, a link stays or git refuses, leave the worktree and name it, with why, in
`Checkout untouched`. Delete only paths you created in this dispatch; never delete recursively
through a link.
