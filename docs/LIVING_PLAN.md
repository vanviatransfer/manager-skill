# manager-skill — Living Plan: token economy

> Single source of intent for this work. Every phase PR updates its own status line here.
> Facts (SHAs, test results) live in git/GitHub; this file only links PRs.

## Goal
Make the manager plugin spend as few tokens as possible per landed phase, without weakening its
invariants (independent exact-SHA review, owner authority, Git safety, required validation).

## Done means
- The orchestrator loads and carries less: the manager skill and both briefs are at least 25%
  shorter in words, and rare material is read on trigger from references.
- Long phases rotate to a fresh implementer instead of growing one context without bound; subagents
  have a compaction cap; the fix-round brake defaults to 5.
- Independent same-shape phases can run in series on one implementer, each PR reviewed at its own
  exact SHA with its own verdict.
- The run-start advice no longer pushes a large auto-compact window.

## Scope
In: plugins/manager-plugin (skills/manager and its references, agents,
skills/living-plan/references/plan-template.md), the root README.md and
.claude-plugin/marketplace.json, docs/TODO.md.
Out (deliberately not doing now):
- delta-only re-review (weakens review independence; full review stays every round);
- skipping the reviewer's own first validation run (required validation);
- one combined verdict for several PRs (exact-SHA review is per PR).

## Constraints and project rules
- Rules: this repository is public: no project-specific details. Markdown lines at most 100
  characters, except frontmatter and code-block templates. Do not reflow paragraphs a phase doesn't
  change; never merge a heading or a list into a paragraph.
- Validation: `python3 -m unittest discover -s plugins/manager-plugin/hooks`,
  `python3 -m unittest discover -s plugins/manager-plugin/skills/code-map/scripts`,
  `python3 -m unittest discover -s plugins/manager-plugin/skills/self-training-skills/scripts`,
  `claude plugin validate plugins/manager-plugin`.
- Merge: squash via PR, pinned to the reviewed SHA.
- Version: only P5 bumps `plugins/manager-plugin/.claude-plugin/plugin.json` (to 0.7.0), so the
  other phases don't conflict there.

## Model strategy
Model strategy: Opus — scope: run R2026-11-15-0000 — owner: "sonnet kullanma opus kullan"

## Binding decisions
- B1. Every rule text that encodes an invariant is moved, never reworded weaker: exact-SHA review,
  owner authority, Git safety, required validation, the plan-at-base reads. (owner, 2026-11-15:
  "token tasarrufu ... unutma" with the invariants kept)
- B2. Measured facts used for decisions (small samples): restricted agents start at about 9–14k
  tokens and general-purpose about 77k (measured once, one session); an implementer phase median
  is about 207k (Sonnet, n=5) / 353k (Opus, n=11) and 61% of phases need 2+ review rounds (one
  project's run records); `subagent_tokens` is cumulative usage, not context size (CLI binary).
  The thresholds in P1–P4 (25%, 3 rounds, about 400k, 3-phase series, the window caps, 200–300k)
  are design choices to be checked against later run records, not measurements. (orchestrator,
  2026-11-15)

## Phases

Status values: `todo` · `in progress (PR #n)` · `done (PR #n)` · `blocked (Dn)`
Fix-round limit per phase: 5

### P1. Move rare manager sections into references
Status: done ([PR #29](https://github.com/vanviatransfer/manager-skill/pull/29))
Objective: the manager skill keeps only what every run needs; rare sections live in
`skills/manager/references/` and are read when their trigger applies.
Scope: `plugins/manager-plugin/skills/manager/SKILL.md`, new files in
`plugins/manager-plugin/skills/manager/references/`. Candidates: code-map check details, plan-only
and specification PRs, no-report recovery, integration and landing branches (merge, rebase,
fast-forward), recurring blocker class, run-record format, session-check details, self-training
pointer. Out of scope: rule changes (P2).
Depends on: none
Risk: standard — text moved, rules unchanged.
Acceptance: SKILL.md word count at least 25% below 7,383; each moved section leaves a one-line
pointer naming its trigger and file; every moved rule exists in exactly one place; the dispatch,
review and landing invariants are unchanged in meaning; the skill says to re-read a reference after
a compaction when its trigger still applies.
Validation: standard.
Notes: B1. Keep step numbering and section headings that other files cite.

### P2. Slim and split the briefs; short implementer return
Status: todo
Objective: each subagent loads only the brief parts its dispatch needs; the implementer returns a
short report and writes the full one to a file.
Scope: `plugins/manager-plugin/skills/manager/references/implementer-brief.md`,
`reviewer-brief.md`, new rare-case files beside them (worktree and junction cleanup, code-map setup
PR, plan-only PR, self-training records, vault rules), each read only when its dispatch field or
condition is set. The implementer's full report goes to a file outside the repository whose path the
orchestrator passes; the return keeps RESULT, Phase, PR, Branch, Base SHA, Candidate SHA, a one-line
validation summary, Blocker / decision needed, and the report path. Add a `Handoff:` note format
(PR, branch, candidate SHA, blockers fixed and open, next step) the implementer writes when asked.
Out of scope: SKILL.md (P3 adapts the orchestrator side).
Depends on: P1 (both add files to `skills/manager/references/`: P2 uses its own file names and
links to P1's files instead of restating a rule)
Risk: standard — moves text; the report fields the orchestrator checks stay in the return.
Acceptance: each brief at least 25% fewer words; the dispatch-field block stays at the top; the
reviewer's verdict format is unchanged and stays inline; nothing an invariant needs is lost.
Validation: standard.
Notes: B1.

### P3. Loop rules for tokens
Status: todo
Objective: the orchestrator spends fewer rounds and smaller contexts.
Scope: `plugins/manager-plugin/skills/manager/SKILL.md` and the references from P1/P2:
- default fix-round limit 5 (plan or project limits still win), with the approach question at
  round 3;
- implementer rotation: after 3 resumed rounds in one phase, or about 400k cumulative
  `subagent_tokens`, the next round goes to a fresh implementer with the previous one's `Handoff:`
  note and the `Fix round` field, never a transcript;
- series mode: up to 3 ready, independent, same-shape `standard` phases go to one implementer in
  sequence, each from the default head on its own branch and PR; each PR gets its own fresh
  reviewer dispatch, exact-SHA verdict and landing; the series stops at a rotation trigger, a
  blocker or an owner decision; never one verdict for several PRs;
- every dispatch states `model` (and `effort` when the strategy sets one) explicitly;
- the session check recommends an orchestrator window of 200–300k (`/autocompact 250k`) instead of
  600k, leaves an owner's own value alone, and doesn't claim it covers subagents;
- step 0 reads the plan's headings, remaining phases, binding decisions, open and decided owner
  decisions, the model-strategy record and the fix-round limit (always, at the default branch),
  and the rest only when needed; the overhead and session checks run once per run;
- after a compaction, re-read the dispatch-field block, the ledger and the working-notes lines;
- the orchestrator side of P2's short return (report path field; facts still checked from git).
Depends on: P1, P2
Risk: critical — changes the loop and its brakes.
Acceptance: each rule stated once; no invariant text weakened (B1); the 600k recommendation is gone
from the skill; series mode cannot land a PR without its own exact-SHA PASS.
Validation: standard.
Notes: B1, B2.

### P4. Agent frontmatter caps
Status: todo
Objective: subagents can't grow or run away unbounded.
Scope: `plugins/manager-plugin/agents/implementer.md`, `reviewer.md`, `worker.md`, `fallback.md`,
`researcher.md`: `autoCompactWindow` (plain integers within 100000–1000000; implementer and worker
300000, reviewer, fallback and researcher 200000) and a generous `maxTurns` safety cap that a
normal phase never reaches. No default `model` in frontmatter (the dispatch sets it). One line in
each body: state lives in git and the plan; after a compaction re-derive it from them.
Depends on: none
Risk: critical — a wrong cap can break phases.
Acceptance: `claude plugin validate` passes; the fields are confirmed honoured for plugin agents
from the CLI (binary schema or loader), or the phase says what is unverified; caps documented.
Validation: standard.
Notes: B2.

### P5. README, TODO and version
Status: todo
Objective: the documentation matches the new behaviour.
Scope: `README.md`, `docs/TODO.md`, `plugins/manager-plugin/.claude-plugin/plugin.json` (0.7.0),
`.claude-plugin/marketplace.json` description if it changes, and
`plugins/manager-plugin/skills/living-plan/references/plan-template.md` (fix-round limit 12 → 5).
Depends on: P1, P2, P3, P4
Risk: standard — docs only.
Acceptance: no stale mention of 600k or 12 rounds anywhere in the repository outside this plan;
rotation, series mode, caps and short returns described with their limits (`subagent_tokens` is
cumulative; the caps' effect is unmeasured).
Validation: standard.
Notes: B2.

## Change log
- 2026-11-15: plan created from a docs/binary study, a GitHub study and a repository audit.

## How to keep this plan alive
- A phase PR updates its own status line and links itself; other status lines only to correct facts.
- Facts that change later phases → update those phases in the same PR and add a change-log line.
- Decision, binding-decision and model-strategy records change only as the manager's Plan records
  say.
- Never copy SHAs or test output into the plan beyond a PR link.
