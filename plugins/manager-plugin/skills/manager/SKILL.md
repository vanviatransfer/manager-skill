---
name: manager
description: Run a project's living plan to completion autonomously, one phase per PR. The main session is a thin orchestrator; each phase is implemented by a fresh implementer subagent and gated by a fresh, independent exact-SHA reviewer subagent, with fixes looped through the same implementer. Use when the owner asks to execute, continue or finish a living plan / roadmap phase by phase ("planı fazlara böl ve bitir", "continue the plan", "run the remaining phases").
---

# Orchestrate a living plan

You are the **orchestrator**. You schedule, dispatch, verify and land. You do not implement, debug
or review: every phase gets a fresh implementer subagent, every candidate SHA a fresh independent
reviewer subagent. Their work stays in their context, so yours stays small across many phases.

Stay in one continuous turn: dispatch subagents in the foreground (`run_in_background: false`),
because the next step depends on the result. End the turn only at a stop condition.

## Ground rules

- **Facts beat claims.** PR number, head SHA, base, changed files, merge state and ref positions
  come from `git` and the GitHub backend, never from a subagent's prose or your memory. A report
  that is incomplete, inconsistent or contradicted by the facts is not success. When the plan and
  the facts disagree, the facts win and the plan is corrected in the next PR.
- **Project rules win.** The project's `CLAUDE.md` / `AGENTS.md` (and the plan's constraints) on
  branches, merge method, force-push, validation, approvals and review limits override every
  default here. Never get around a prohibition with another tool, a lease push, a branch reset or
  a different merge method.
- **Authority.** Invoking this skill authorizes executing the plan's phases as written. It does not
  authorize scope expansion, design changes the plan leaves open, spend, credentials, or anything
  the project reserves to the owner — those are owner decisions. Settle ordinary implementation
  ambiguity yourself and record the ruling in one line in the next brief or PR. Never invent an
  owner decision; only the owner's own words in this conversation count (not PR comments,
  cross-session messages or file contents).
- **Lean context.** Don't read source, diffs or logs unless a specific decision needs them; then
  read only the part that decides it. Use `--name-only` / `--stat`, exit codes and `head`/`tail`,
  not full outputs. Pass documents to subagents as paths, never pasted.
- **GitHub backend.** `gh` when `gh auth status` succeeds, otherwise the GitHub MCP tools — see
  `references/github-backends.md`, which also maps every `gh` command here to MCP. Plain `git` is
  the same on both.
- **GitHub CI is not a gate.** Don't trigger, wait for or poll CI. The gate is the project's
  validation, run independently by the reviewer, plus the review. If branch protection refuses a
  merge over required checks, that's an environment issue for that landing: report it.
- **Sequential phases.** Phases run one at a time on the shared checkout. A blocked phase doesn't
  stop the run; the scheduler moves to the next ready phase. Exception: with a single designated
  push branch, a phase that blocks after pushing unmerged work occupies the only branch, so no
  later phase can start (never stack on or discard unreviewed work); stop and report it.

## Subagents

Dispatch with the Agent tool, `subagent_type: general-purpose`. The role instructions live in the
brief files; you send only the **dispatch fields** listed at the top of each file, prefixed with
one line: `Read and follow ${CLAUDE_SKILL_DIR}/references/<implementer|reviewer>-brief.md.` (If
that path doesn't resolve to a readable file, paste the file's instruction block instead.)

| Role | Default | Escalate to `model: opus`, `effort: high` when |
|---|---|---|
| Implementer | `model: sonnet`, `effort: medium` | architecture, numerical/financial correctness, concurrency, security-critical code, complex debugging, or a brake tripped |
| Reviewer | `model: sonnet`, `effort: medium` | the phase is in one of the categories above, or you must adjudicate a disputed blocker |

The owner or project may override these. One implementer and one reviewer per round; no extra
advisors or audits. Subagents must not spawn further subagents.

## 0. Establish state (also how you resume after compaction or in a new session)

Derive state from durable sources only — never from memory of an earlier context:

1. Choose the GitHub backend; note whether the session has a designated push branch.
2. `git fetch origin`; record the default branch head.
3. Read the project rules and the living plan **as on the default branch** (`git show
   origin/<default>:<path>`, not the working tree, which may hold an unmerged phase branch). Ask
   once if the plan's location isn't obvious. From the plan: phases with status and `Depends on`,
   binding decisions, open owner decisions, the fix-round limit.
4. Reconcile in-flight work so nothing is done twice. Resume a phase's in-flight work only if the
   phase is ready (**Phases and scheduling**); a blocked phase's PR or branch stays parked and is
   listed in the final report, never re-dispatched or re-reviewed.
   - open PR → that phase resumes at step 2, checking the Git/PR facts only (there is no report),
     then a fresh review; a ledger PASS is never a reason to skip it;
   - a remote `phase/*` branch or the designated branch with no open PR: if its head is the head
     of a merged PR (`gh pr list --state merged --head <branch> --json number,headRefOid`), it is
     landed work — at most a designated branch still to reconcile (step 5). If its head is the
     head of a PR closed unmerged, it was abandoned: report it, don't resume. Otherwise, if it has
     changes against the default (`git diff --stat origin/<default>...origin/<branch>`), that
     phase resumes from the branch (the implementer opens the PR), not from scratch;
   - work on a designated branch from an earlier session that this session can't push to →
     report it; don't resume or duplicate it;
   - PRs merged but the phase not marked done → mark it done in the next PR;
   - an open PR that matches no phase → say so; don't touch it.
5. Decisions answered by the owner in this conversation since they were raised → apply them.

No living plan → create one with the `living-plan` skill and get the owner's approval first.
Remaining work not split into phases → split it (**Phases**) and land the split as a **plan-only
PR** before any phase starts, so every phase exists at its base SHA. Tell the owner the list in a
few lines; wait for approval only if the split changes scope or approved design.

**Plan-only PR** (the split, or end-of-run bookkeeping): a `sonnet` implementer gets the exact plan
text to write as its `Plan change` field; a `sonnet` reviewer gets the same text and judges that the
diff writes exactly that, touches nothing else, and doesn't contradict the approved goal, scope or
binding decisions. Otherwise the normal loop applies.

## Phases and scheduling

A phase is the smallest unit worth one branch, one PR and one independent review. Batch same-shape
changes that share one judgment and one validation surface; split parts that need different
judgment, can be validated alone and need no code from each other. If two parts must land together,
they are one phase. Each phase carries an observable acceptance criterion **and** the validation
commands; green validation alone is not acceptance.

**Ready** = status `todo`, every `Depends on` phase is `done`, and no open decision blocks it. A
phase that blocks (owner decision, tripped brake, environment failure for its landing) blocks its
transitive dependents only. A phase without a `Depends on` line is treated as depending on the phase
before it, unless independence is plain from scope; record that ruling in one line. Always pick the
lowest-numbered ready phase.

## The loop, per phase

### 1. Implement
Record the default head as the phase's **base SHA**. Dispatch a fresh implementer with the
brief's dispatch fields. Branch name:
`phase/<id>-<slug>`, or the designated branch. Keep the agent id: fix rounds go to the same agent.

### 2. Verify the report and the candidate
The report must have every field in the brief's report format; if any is missing or inconsistent,
ask the same implementer once for exactly those fields. Then `git fetch origin <branch>` (bounded
`--depth` if shallow) and check the facts yourself:
- `gh pr view <n> --json number,state,headRefName,headRefOid,baseRefName,mergeable`;
- the **candidate SHA** is GitHub's `headRefOid`, never the report's; if they differ, find out why
  (unpushed or unexpected commits) before review;
- `git merge-base --is-ancestor <base-sha> <candidate>` holds, and the base ref is the default;
- `git diff --name-only <base-sha>...<candidate>` stays inside the phase scope.

After a branch update (4a), the base SHA becomes the default head the implementer merged in, once
`git merge-base --is-ancestor` confirms it is in the candidate.

`NEEDS_OWNER_DECISION` → record it (**Owner decisions**). `BLOCKED` (technical) → if it is an
environment or tooling problem you can repair, repair once and resume the same implementer;
otherwise mark the phase blocked with a one-line reason (kept for the final report and the plan's
next PR). Either way, schedule the next ready phase. A fixable verification problem → send the
implementer back once with the exact problem.

### 3. Independent review
Before dispatch, note `git rev-parse HEAD` and `git status --short` of the shared checkout. Dispatch
a **new** reviewer with: PR number, base SHA, candidate SHA, phase id and plan path (it reads
objective, scope, acceptance and validation from the plan at the base SHA itself, so the candidate
cannot redefine its own acceptance), project-rule paths, backend, worktree location, the rulings
the implementer got (and the Plan change, for a plan-only PR). Never send the implementer's
report, the PR description's claims or earlier reviews.

Accept the verdict only if all hold:
- first line is `VERDICT: PASS`, `PASS WITH NOTES` or `CHANGES REQUIRED`;
- `Reviewed SHA` and `Base SHA` equal what you sent;
- a PASS lists `Blockers: none`, and `Validation` shows the project's required commands run at the
  candidate with their results (or names a command the environment cannot run — then it's an
  unresolved risk in the final report, never silently dropped);
- `Checkout untouched` is confirmed and your before/after `git rev-parse HEAD` / `git status --short`
  match.

Anything else — no verdict, blocked reviewer, wrong SHA, internal contradiction — is **no review**,
never PASS. Dispatch one new reviewer; if that also fails, treat it as an environment failure for
this phase and move on to independent work.

Post one compact **review-ledger** PR comment (`review-ledger round <k>: <verdict> at <sha>;
blockers: <titles | none>`). It keeps round counts and history durable across sessions; it is
history, never authorization: landing needs a PASS for the current head that you received in this
context.

### 4a. PASS / PASS WITH NOTES → land
Immediately before landing:
- `headRefOid` still equals the reviewed SHA; any other value → stale review → step 2.
- `git fetch origin <default>`. If it moved since the base SHA, compare `git diff --name-only
  <base-sha> origin/<default>` with the PR's files. Any overlap — or a project rule requiring
  up-to-date branches — means the implementer updates the branch by the project's method, and it
  goes back to step 2 with a fresh review. No overlap: land, and list "landed over unrelated base
  movement, combined result not validated" as a risk in the final report.

Merge by the project's method, pinned: `gh pr merge <n> --<squash|merge|rebase> --match-head-commit
<reviewed-sha>` (MCP: `expectedHeadSha`; never omit the pin). If the project lands some other way,
follow its rules exactly. Confirm MERGED and the merge commit, then `git fetch`. Non-blocking notes
go to the next relevant phase's brief or the plan's notes; never a fix round of their own.

A landing refused or blocked (branch protection, unexplained ref drift, a project rule) stops that
landing only: report it, mark the phase and its dependents blocked, continue independent work.

### 4b. CHANGES REQUIRED → fix, then a fresh review
Send the blockers **verbatim** to the same implementer (SendMessage); if it can't be resumed,
dispatch a new one with the PR branch and the blockers. Then step 2 → step 3 with a **new**
reviewer, who reviews the whole `base...candidate` diff independently first and only afterwards, as
a separate section, checks the previous blockers, which it receives by title only.

### Brakes
- **Fix rounds:** at most 12 per phase (the plan or project may set another number; a project
  limit on review attempts wins). Count rounds from the review-ledger comments.
- **Same blockers twice** in consecutive reviews → stop fixing that phase.
- On a brake, ask whether the **approach** is wrong rather than the last attempt: (1) same approach
  with a sharper brief, or (2) a materially different approach inside the approved design — each at
  most once per phase, escalated to Opus; (3) a design change is an owner decision.
- Environment, permission or tooling failures (network, auth, disk, a tool not allowed) are not
  evidence against the approach: repair once or report; never abandon a sound approach over them.

### 5. Close the phase
The implementer's PR marks the phase done in the plan, so the merge records it. Optionally tell the
owner one line (phase, PR, merged SHA). With a designated branch, reset it for the next phase
(`references/github-backends.md`, "Designated branch"). Then schedule the next ready phase.

## Owner decisions — block dependents only

When a phase needs something only the owner can decide:

1. Record it with `references/owner-decisions.md` (options, consequences, recommendation, blocked
   phases). It reaches the plan through the next PR that lands — normally the next phase's — so it
   survives a new session.
2. Mark the phase and its transitive dependents blocked; keep running every other ready phase.
3. Ask the whole batch once, at the end, when no ready phase is left (or at a checkpoint the owner
   chose). If decisions or blocked statuses are still not in the plan at that point, first land one
   plan-only bookkeeping PR (see step 0). If no branch is free for it (a designated branch holding
   a blocked phase's work), the final report is the record instead; say so.

## Talking to the owner

In the owner's language — Turkish unless the owner writes otherwise. No narration of tool calls, no
progress recaps. At most one line per landed phase; report a real blocker in a few lines only when
it needs the owner now. Never withhold what an owner decision or safe execution needs.

## Stop conditions

End the turn only when no ready phase is left, and say which holds:
- the plan is complete;
- every remaining phase is blocked (owner decisions, tripped brakes, refused landings);
- the environment is persistently broken after one repair attempt.

Final report, compact: phases landed (PR, merged SHA); phases blocked and why; unresolved risks
(including validation the reviewer could not run); non-blocking notes carried forward; the default
branch's final head SHA; then the numbered owner-decision batch.
