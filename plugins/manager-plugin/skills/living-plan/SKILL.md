---
name: living-plan
description: Create (or rebuild) a project's living plan — one markdown file holding the goal, scope, binding decisions, phases with acceptance criteria and validation, status, and open owner decisions — in the shape the `manager` skill executes. Use when the owner asks to make a plan, a living plan, a roadmap or a migration plan for a project, or to turn an idea/spec/backlog into phases ("living plan yap", "planla", "make a plan for this").
---

# Create a living plan

A living plan is the single durable document a project is driven from. It says **what** we are
building and **why**, the decisions that bind the work, and the remaining work as phases small
enough for one PR each. It is updated by every phase that lands, so it is always the current
intent. The `manager` skill runs it; this skill writes it.

The plan holds **intent**. Facts like SHAs and test results live in git and GitHub; the
plan only links to PRs.

Talk to the owner in the owner's language. Write the plan in the language the project's docs use
(ask if unclear).

## 1. Understand before writing

Ground yourself first, cheaply:
- Read the project rules (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING`), the README, the vault's
  `index.md` if the project has one (`docs/vault/`, or the path the project's rules name), and any
  existing plan, roadmap, spec or issue the owner points at.
- Look at the code's shape: stack, layout, how it's tested and validated, how PRs are merged.
- `git log --oneline -20` and the open PRs for what's happening now (`gh pr list` when `gh` is
  authenticated, otherwise the GitHub MCP `list_pull_requests` tool, as in a cloud session).

Then ask the owner what you couldn't find — **in one batch**, numbered, with your best guess for
each so they can just confirm. Typical gaps: the goal in one sentence, what "done" looks like, hard
constraints (deadline, budget, stack, compatibility), what is explicitly out of scope, who decides
what. Don't ask what the repo already answers. If the owner gave a detailed brief, you may need no
questions at all.

## 2. Shape the work

- **Goal and done.** One or two sentences each. "Done" must be observable.
- **Binding decisions.** Choices already made (by the owner or the project) that phases must not
  re-open. Number them so phases can cite them.
- **Phases.** A phase is one coherent deliverable worth one branch, one PR and one independent
  review — not the smallest possible unit. Every phase pays a fixed cost: two fresh subagents load
  the rules, the plan and the code, and the full validation runs twice. So batch same-shape work
  (several screens, endpoints or migrations of one kind) into one phase while it keeps one
  judgment, one validation surface and a diff one reviewer can check in one pass. Split when parts
  need different judgment or risk level, can be validated alone, or the diff would be too large to
  review well. Several steps in one change are not a reason to split.
- **Risk.** Mark each phase `Risk: standard` or `Risk: critical` (architecture, numerical or
  financial correctness, concurrency or locking, security, personal data), with the reason when
  critical. The manager's model strategy uses it.
- **Validation cost.** List the commands every run of the phase needs, and mark expensive ones that
  only matter for some changes with a trigger in parentheses after the command, naming an
  observable property of the diff (paths or code areas), e.g. `(when: migrations or locking code
  change)`. If a change could affect a suite indirectly (shared helpers, config, dependencies),
  don't gate it.
- **Order by dependency, not by taste.** If B needs A's code, B comes after A. If two parts must
  land together, they are one phase. Put risky unknowns early (a spike or proof phase is fine).
- **Wide refactor** (a rename or retype that breaks call sites everywhere) whose single diff would
  be too large to review or can't land green: expand (add the new form beside the old) → migrate in
  batches, each a phase sized for one reviewer pass and depending on expand → contract (remove the
  old form), which depends on every migrate phase and has an observable acceptance (no caller of the
  old form left).
- **Every phase gets** an objective, scope (and out-of-scope when it matters), `Depends on`
  (phase ids, or `none`; the manager schedules by it and keeps running independent phases while
  others are blocked), an observable acceptance criterion, and the exact validation commands.
  Green validation is not acceptance; write both.
- **Owner decisions.** Anything only the owner can decide becomes a numbered open decision with
  options and your recommendation, and the phases it blocks are marked. Don't bury a decision as a
  placeholder inside a phase.
- **Right-size the plan.** A two-day job may be three phases and a page. A migration may be thirty
  phases in groups. Depth follows risk, not habit.

## 3. Write it

Use `references/plan-template.md`. Default path: `docs/LIVING_PLAN.md`, unless the project already
has a plan location or the owner names one. If a plan already exists, update it in place: keep
completed phases and decided items, re-plan only what remains, and say what changed.

## 4. Review with the owner

Show a short summary, not the whole file: goal, number of phases with their titles, the first two
or three in a line each, and the open decisions with your recommendations. Ask for approval or
changes. Approval of the plan is not authorization to execute it — unless the owner says to go,
stop here.

Commit the plan following the project's rules (usually its own small PR). When the owner wants
execution, hand over to the `manager` skill.

## Keeping it alive

These rules go into the plan itself so every implementer follows them:
- Each phase's PR updates that phase's status line and links the PR; other status lines change
  only to correct a fact (e.g. a phase merged but not marked done).
- New facts that change remaining phases → update those phases in the same PR, and note it in the
  change log.
- A newly found owner decision → add it to the open decisions, mark the blocked phases. An answer
  moves it to "Decided" with the owner's exact words and date, and unblocks those phases. Decision,
  binding-decision and model-strategy records change only as the manager's `Plan records` say.
- Never copy SHAs or test output into the plan beyond a PR link; those are facts that
  live in git and GitHub.
