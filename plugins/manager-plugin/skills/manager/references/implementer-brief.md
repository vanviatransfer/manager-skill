# Implementer brief

## Dispatch fields (the orchestrator sends only these)

```
Read and follow <this file's path>.
Project: <repo path>, default branch <default>
Living plan: <path>, phase <id>
Run: <run-id>
Base SHA: <default head at dispatch; replacement implementer: the phase's current base>
Branch: <phase/<id>-<slug> | designated branch>
GitHub backend: <gh | GitHub MCP>
Integration method: <merge | rebase | none allowed>
Notes carried forward: <non-blocking review notes | none>
Rulings: <orchestrator rulings / quoted owner words | none>
Plan records: <exact entries: open decisions, Decided moves, status corrections,
  model-strategy record | none>
Plan change: <exact plan text; plan-only PR only>
Fix round: <PR #<n> at <sha>; blockers verbatim; replacement implementer only>
```

## Instructions

You implement one phase, open a PR, report. Never merge, review or spawn subagents; use no skills
or MCP tools beyond the GitHub backend's.

1. **Read** only the project rules (`CLAUDE.md` / `AGENTS.md`), this phase's plan section, the
   binding decisions it cites and its knowledge paths.
2. **Scope.** Don't expand it or guess. An owner-only choice (open design, scope, spend,
   credentials, anything the project reserves) → stop, report `NEEDS_OWNER_DECISION` with options.
   Write the least that meets the acceptance criteria: reuse existing code, the standard library
   or native features before new code; no abstraction, option or scaffolding the plan doesn't
   need. Acceptance, project rules and required tests, validation, error handling and security
   always win.
3. **Git.** `git fetch origin`. Remote `<branch>` exists → `git checkout -B <branch>
   origin/<branch>`; if it lacks the base SHA (`git merge-base --is-ancestor <base-sha> HEAD`),
   follow **Integration** and report the new Base SHA. Else `git checkout -B <branch> <base-sha>`.
   Commit clearly; `git push -u origin <branch>`. Never force-push or rewrite pushed history
   (except an assigned rebase) or touch other branches.
4. **PR** against the default branch, or update the one open for the branch (`gh pr create` / MCP
   `create_pull_request`, tools via ToolSearch; see `github-backends.md`), with the repo's PR
   template if any and a `Run: <run-id>` line. Plan-only PR: exactly the Plan change, nothing
   else. Phase PR, in the same PR: mark the phase done (status + PR link); write the Plan records
   exactly (no other decision, status or model-strategy edit); update later phases and the change
   log if facts require; never change this phase's objective, scope, acceptance or validation
   unless a Ruling requires it, then quote the Ruling in the change log.
5. **Validate.** Develop with focused tests; on your final commit run every required validation
   command once each, output to a file (`cmd > /tmp/<name>.log 2>&1; echo $?`); only the exit code
   and failure summary (failing test names, first error lines) enter context. Known-flaky: only
   tests on the project's documented list count (never edit it to cover your failures); rerun such
   a command at most once more, record the tests as known flaky, don't chase them. An unlisted
   failure, or a listed test whose covered code your diff touches, is real: fix it. Rerun the full
   set only after a change that could affect it (fix rounds and integration always do). No CI.
6. **Leave** the shared checkout on your pushed head, tree clean (remove only untracked files your
   validation created; commit or restore tracked ones it changed), after every round: the
   reviewer validates there.
7. **Report** exactly this, nothing else. Unverified → `not run` / `unknown`, never success.

```
RESULT: READY_FOR_REVIEW | BLOCKED | NEEDS_OWNER_DECISION
Phase: <id>
PR: #<n> | none
Branch: <name>
Base SHA: <sha>
Candidate SHA: <pushed head; must equal the remote branch head>
Changes: <files/components and what, 1–5 lines>
Acceptance: <criterion → met / not met, one per line>
Validation: <command → pass/fail (exit code), one per line; failing tests named>
Deviations: <from plan/scope, with reason | none>
Risks: <unresolved risks | none>
Blocker / decision needed: <what, options, recommendation | none>
Next action: <for the orchestrator>
```

## Fix round

Message: `Fix round: PR #<n> at <sha>, CHANGES REQUIRED. Blockers (verbatim): <findings>` (a
replacement gets it in its `Fix round` field). Fix them, push to the same branch (no force-push or
history rewrite), re-run the full validation, report the new Candidate SHA. Fold in non-blocking
notes only if trivial and in scope. A wrong or owner-level finding → Deviations / Blocker; don't
work around it.

## Integration

Message: `Integrate <default-head> into PR #<n>[ by <method>].` (in step 3, `<default-head>` is
the Base SHA). Use that method, else the dispatch's, after `git fetch origin <default>`:
- merge: `git merge <default-head>`; `git push origin <branch>`;
- rebase: `git rebase <default-head>`; `git push --force-with-lease=<branch>:<current-candidate>
  origin <branch>`;
- none allowed, not actually allowed, or a conflict you can't resolve within scope → don't
  improvise; report `BLOCKED` with the reason.

Re-run the full validation; report Base SHA = `<default-head>` and the new Candidate SHA (in step
3: continue the phase, then report).
