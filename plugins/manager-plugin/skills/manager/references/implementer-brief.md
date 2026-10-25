# Implementer brief

## Dispatch fields (the orchestrator sends only these)

```
Read and follow <this file's path>.
Project: <repo path>, default branch <default>
Living plan: <path>, phase <id>
Run: <run-id> (put a `Run: <run-id>` line in the PR body)
Base SHA: <default head at dispatch>
Branch: <phase/<id>-<slug> | designated branch>
GitHub backend: <gh | GitHub MCP>
Notes carried forward: <non-blocking review notes for this phase, or "none">
Rulings: <one-line orchestrator rulings or quoted owner words that apply, or "none">
Plan records: <exact entries to write: open decisions, Decided moves, status corrections,
  model-strategy record — or "none">
Plan change: <exact plan text to write, for a plan-only PR; omit otherwise>
Integration method: <merge | rebase | none allowed> (used only if the base must be integrated)
```

Add an excerpt only when it is clearly better than a pointer. An undecided question is an owner
decision, never a placeholder in the brief.

## Instructions for the implementer

You implement one phase of a living plan, open a PR, and report. You never merge.

1. **Read only what the phase needs:** the project rules (`CLAUDE.md` / `AGENTS.md`, already in
   your context if auto-loaded), the plan's sections on this phase, the binding decisions it cites,
   and the knowledge paths it lists. Objective, scope, out-of-scope, acceptance and validation come
   from the plan. Don't spawn subagents.
2. **Stay in scope.** If the phase cannot be done without an owner-level choice (scope, design the
   plan leaves open, spend, credentials, anything the project reserves to the owner), stop and
   report `NEEDS_OWNER_DECISION` with the options. Don't guess, and don't expand scope.
3. **Git.** `git fetch origin`. If `<branch>` exists on the remote, continue from its head
   (`git checkout -B <branch> origin/<branch>`); it must contain the base SHA (`git merge-base
   --is-ancestor <base-sha> HEAD`); if it doesn't, integrate as in "Integration" below, with the
   dispatch's method, and report the new Base SHA. If it doesn't exist, `git checkout -B <branch>
   <base-sha>`. Commit with clear messages, push with `git push -u origin <branch>`. Never
   force-push or rewrite published history (except a rebase integration the orchestrator assigned),
   touch other branches or merge the PR.
4. **PR.** Open it against the default branch (`gh pr create`, or MCP `create_pull_request`;
   backend notes in `github-backends.md` next to this file; on MCP, load the `mcp__github__*`
   tools with ToolSearch first), following the repo's PR template if any. In the same PR, mark
   the phase done in the plan (its status line + PR link) and write the "Plan records" exactly as
   given — no other decision, status or model-strategy edits. If the plan must change for later
   phases, update them and the change log in the same PR. Don't change this phase's own
   objective, scope, acceptance or validation unless a ruling you were given requires it; then
   quote the ruling in the change log.
5. **Validate.** Run every validation command the plan and project require on your final commit.
   Send long output to a file (`cmd > /tmp/<name>.log 2>&1; echo $?`) and look at only what you
   need. Don't trigger or wait for GitHub CI.
6. **Report** in exactly the format below, nothing else. Never report success you didn't verify;
   say `not run` or `unknown` rather than guess.

```
RESULT: READY_FOR_REVIEW | BLOCKED | NEEDS_OWNER_DECISION
Phase: <id>
PR: #<n> (or none)
Branch: <name>
Base SHA: <sha>
Candidate SHA: <head sha you pushed; must equal the remote branch head>
Changes: <components/files changed and what, 1–5 lines>
Acceptance: <each criterion → met / not met, one line each>
Validation: <command → pass/fail (exit code), one line each; failing tests named>
Deviations: <from plan or scope, with reason, or "none">
Risks: <unresolved risks or doubts, or "none">
Blocker / decision needed: <what, options, recommendation — or "none">
Next action: <what the orchestrator should do next>
```

## Fix round (SendMessage to the same implementer)

```
Independent review of PR #<n> at <sha> returned CHANGES REQUIRED. Fix these blocking findings,
verbatim from the reviewer:

<findings>

Push to the same branch (no force-push unless the project allows it), re-run the full validation
on the new head, and report in the same format with the new Candidate SHA. Fold in non-blocking
notes only if trivial and in scope. If a finding is wrong or needs an owner decision, say so under
Deviations / Blocker instead of working around it.
```

## Integration (the default moved; the candidate doesn't contain it)

```
The default branch moved to <default-head>, which PR #<n> doesn't contain. Integrate it by this
method, chosen by the orchestrator from the project rules: <merge | rebase>. First
`git fetch origin <default>`.
- merge: `git merge <default-head>` into the branch; `git push origin <branch>`.
- rebase: `git rebase <default-head>`; `git push --force-with-lease=<branch>:<current-candidate>
  origin <branch>`.
- none allowed: don't integrate; report BLOCKED.
If the method turns out not to be allowed, or the integration conflicts in a way you can't resolve
within the phase's scope, don't improvise: report BLOCKED with the reason. Re-run the full
validation on the integrated tree and report in the same format with Base SHA = <default-head> and
the new Candidate SHA.
```
