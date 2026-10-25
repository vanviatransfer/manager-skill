# Living plan template

Copy the shape, not the wording. Drop sections that would be empty; don't pad.

```markdown
# <Project> — Living Plan

> Single source of intent for <project>. Every phase PR updates its own status line here.
> Facts (SHAs, test results) live in git/GitHub; this file only links PRs.

## Goal
<One or two sentences: what we're building and why.>

## Done means
- <Observable outcome 1>
- <Observable outcome 2>

## Scope
In: <...>
Out (deliberately not doing now): <... and why, one line each>

## Constraints and project rules
- Rules: see `<CLAUDE.md / AGENTS.md>` (binding for every phase).
- Validation: `<commands every phase must pass>`
- Merge: <method, e.g. squash via PR>
- <deadline / budget / compatibility / stack constraints>

## Model strategy
<Only if the owner set one; the manager records each run's choice here.>
Model strategy: <Sonnet | Opus | mixed: role/condition → model> — scope: run R<YYYY-MM-DD-HHMM> | standing — owner: "<quote>" (<date>)

## Binding decisions
- B1. <decision> — <why, one line> (<who, date>)
- B2. ...

## Phases

Status values: `todo` · `in progress (PR #n)` · `done (PR #n)` · `blocked (Dn)`
Fix-round limit per phase: 12

### P1. <title>
Status: todo
Objective: <one deliverable>
Scope: <files / areas>. Out of scope: <if it matters>
Depends on: <phase ids or "none" — required; the manager schedules by it>
Acceptance: <observable result>
Validation: <commands, or "standard">
Notes: <decisions cited (B1, D2), risks, knowledge paths>

### P2. <title>
...

## Open owner decisions

### D1. <question>
Blocks: P<n>
Context: <two or three sentences>
Options:
  A. <option> — <consequence>
  B. <option> — <consequence>
Recommendation: <A/B and why>
Raised: <date>

## Decided
- D0. <question> → <answer> — owner: "<exact words>" (<date>, in the session conversation). Unblocks: P<n>.

## Notes carried forward
- <non-blocking review notes worth folding into a later phase, with the phase id>

## Change log
- <date>: plan created.
- <date>: P4–P6 re-planned after <fact>; P5 superseded.

## How to keep this plan alive
- A phase PR updates its own status line and links itself; other status lines only to correct facts.
- Facts that change later phases → update those phases in the same PR and add a change-log line.
- A new owner decision → add it under Open owner decisions and mark blocked phases; an answer moves
  it to Decided (owner's exact words, date) and unblocks them. Decision and model-strategy records
  change only through the manager's Plan records.
- No SHAs or test output here beyond PR links.
```
