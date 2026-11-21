# manager-skill — Living Plan: 0.9.0

> Single source of intent for this work. Every phase PR updates its own status line here.
> Facts (SHAs, test results) live in git/GitHub; this file only links PRs.
> The previous plan (0.7.x token economy) is in `docs/archive/LIVING_PLAN-0.7-token-economy.md`.

## Goal
Cut the orchestrator's token use further and make the manager loop survive compaction, using the
findings of two independent audits and a research report on 0.8.x (see the phases), without
weakening the invariants (independent exact-SHA review, owner authority, Git safety, required
validation).

## Done means
- After a compaction the orchestrator still has every rule it needs: the manager skill fits the
  re-attach budget, and compaction hooks keep the working-notes state.
- The orchestrator's own token use is measured per run, and its context size is watched.
- Plans are validated and a phase's brief section is extracted by a script instead of read in full.
- Reviewers get a capped list of what a diff touches from the code map.
- The plugin's invariants are covered by eval cases.

## Scope
In: plugins/manager-plugin (skills, references, agents, hooks, scripts, tests), README.md,
.claude-plugin/marketplace.json, docs/TODO.md, this plan.
Out (deliberately not doing now):
- delta-only re-review (weakens review independence);
- a 1-hour cache TTL for subagents (measured: costs more for reviewers and implementers);
- dynamic workflows for the phase loop (large, unverified with plugin agents; revisit later).

## Constraints and project rules
- Rules: this repository is public: no project-specific details. Markdown lines at most 100
  characters, except frontmatter and code-block templates. Do not reflow paragraphs a phase doesn't
  change; never merge a heading or a list into a paragraph. Plugin code: Python standard library
  only, Python 3.8+, no network; hooks fail open and write nothing inside any repository.
- Validation: `python3 -m unittest discover -s plugins/manager-plugin/hooks`,
  `python3 -m unittest discover -s plugins/manager-plugin/skills/code-map/scripts`,
  `python3 -m unittest discover -s plugins/manager-plugin/skills/self-training-skills/scripts`,
  `python3 -m unittest discover -s plugins/manager-plugin/skills/manager/scripts`,
  `claude plugin validate plugins/manager-plugin` (run Python with `PYTHONDONTWRITEBYTECODE=1`); a
  phase that adds a script folder with tests appends its `unittest discover` command to this
  Validation line in the same PR, so later phases run it too.
- Size ceilings (the test P2 adds for manager SKILL.md, implementer-brief.md, reviewer-brief.md and
  code-map SKILL.md): a later phase whose scope adds a rule to one of these files may raise that
  file's ceiling by what it adds, stated in its PR, or move detail to a trigger file instead.
- Merge: squash via PR, pinned to the reviewed SHA.
- Version: only P8 bumps `plugins/manager-plugin/.claude-plugin/plugin.json` (to 0.9.0).

## Model strategy
Model strategy: Fable xhigh — scope: run R2026-11-20-2300 — owner: "fable xhigh review etsin"

## Binding decisions
- B1. Invariant text is moved, never reworded weaker: exact-SHA review, owner authority, Git safety,
  required validation, the plan-at-base reads — they carry the plugin's guarantees. (owner,
  2026-11-15)
- B2. Plan and vault text is English, whatever language a project's rules name for it — models work
  in English and translation costs tokens. (owner, 2026-11-20: "ingilizce çünkü modeller İngilizce
  düşünüyor, çeviri token harcar")
- B3. Every plugin agent sets `omitClaudeMd: true`; agents read the working repository's rules
  explicitly — no agent may follow another project's rules. (owner, 2026-11-20: "tüm ajanlarda
  varsayılan. Baska proje okunmamali")

## Phases

Status values: `todo` · `in progress (PR #n)` · `done (PR #n)` · `blocked (Dn)`
Fix-round limit per phase: 5

### P1. 0.8.3 follow-ups
Status: done (PR #44)
Objective: close the review notes and audit findings on 0.8.3's own changes.
Scope: plugins/manager-plugin/skills/manager (SKILL.md, references), skills/code-map
(codemap.py session-hook text and rules-hint versioning, SKILL.md, scripts/test_codemap.py),
hooks (codemap-rules-version.sh header, test_prefer_plugin_agents.py plan-read and rules-version
hook tests), skills/self-training-skills SKILL.md, agents, docs/TODO.md:
- the SessionStart rules-version line is information, not an order ("… is older; `<cmd>` updates
  it; a manager run does this in its setup PR");
- an unversioned rules block whose text equals the current template counts as current (the marker
  is rewritten when the block is next written), so 0.8.x repositories don't each pay a setup PR for
  a marker bump; a real text change still triggers it;
- the brake-reset rule stated once (SKILL.md Brakes; owner-decisions.md points to it);
- the awk plan read gets a fallback: if no `## Constraints…` or `## Binding decisions` section is
  printed, `grep -n '^## '` and read them; it also prints the `## Phases` preamble (status values,
  fix-round limit);
- the implementer dispatch gets a `Project rules: <paths>` field like the reviewer's; the
  orchestrator lists every rules file the repository has (CLAUDE.md, AGENTS.md,
  `.claude/CLAUDE.md`, `.claude/rules/*.md`, and the files they import with `@path`), since
  `omitClaudeMd` drops the whole instruction block (B3);
- the final report reads a phase's report file only when its short-return `Risks:` line is not
  `none`;
- step 2's fact checks run in one Bash call (say so);
- self-training skill files and records follow B2 (English);
- `github-backends.md` PR-facts row and SKILL.md's `gh pr view` line agree on `files`.
Depends on: none
Risk: standard — wording and small logic changes; tests cover the rules-version logic.
Acceptance: every listed item done once, all references updated; tests for the identical-text
unversioned block (current) and a changed-text block (outdated); the session-hook line contains no
imperative to commit.
Validation: standard.
Notes: B1, B2, B3.

### P2. Manager skill survives compaction
Status: done (PR #45)
Objective: the manager skill fits the compaction re-attach budget and the loop's state survives a
compaction.
Scope: plugins/manager-plugin/skills/manager/SKILL.md and references/, hooks (hooks.json or the
skill's own `hooks` frontmatter if the installed CLI supports it for plugin skills — verify), tests:
- SKILL.md under 18,000 characters (Claude Code re-attaches the first ~5,000 tokens, ~20,000
  characters, of each invoked skill after a compaction): invariants and the loop skeleton (steps
  0–5 with landing, brakes and stop conditions) stay in the skill; step detail moves to references
  read at the step, each with a one-line pointer naming its trigger;
- step 0 reads the plan's headings and every `Status`/`Depends on`/`Risk` line plus the binding
  decisions, decisions, strategy record and fix-round limit, not every remaining phase's section; a
  phase's section is read (the briefs' awk at the default head) when it is scheduled;
- a PreCompact hook prints instructions to keep the working-notes lines verbatim (≤10,000
  characters), and a SessionStart hook with matcher `compact` prints one line telling the session to
  re-read the manager skill and the references whose triggers apply, both only when a manager run
  is in progress (detect it cheaply, e.g. a marker the skill writes outside the repository; fail
  open);
- a test with size ceilings: manager SKILL.md ≤18,000 characters, implementer-brief.md and
  reviewer-brief.md ≤ their word counts after this phase, code-map SKILL.md ≤20,000 characters.
Depends on: P1
Risk: critical — moves the loop's rules; a lost rule weakens an invariant.
Acceptance: SKILL.md ≤18,000 characters; every moved rule exists exactly once with a pointer from
the skill; no invariant weakened (B1); the hooks are tested (fire only in a manager run, fail open,
write nothing in a repository); the size test passes.
Validation: standard.
Notes: B1.

### P3. Real token accounting
Status: done (PR #46)
Objective: each run records what the orchestrator and every subagent actually spent.
Scope: a stdlib script (e.g. plugins/manager-plugin/skills/manager-retro/scripts/usage.py or under
skills/manager/scripts/) that reads the session transcript and its `subagents/agent-*.jsonl` (+
`.meta.json`) under the Claude config folder (`CLAUDE_CONFIG_DIR` or `~/.claude`), de-duplicates
requests by message id, and prints per agent and for the orchestrator: requests, cache reads, cache
writes by TTL, output, context at return, and cold resumes (a request whose cache read is 0 after a
gap); unknown when files are missing. references/run-record.md and the manager-retro skill use it
(one Bash call at run end and per phase if cheap); record warm/cold resumes and review duration so
rotation can be re-tuned. Also: references/final-report.md points at owner-decisions.md's Plan
records for the end-of-run bookkeeping PR; hooks/test_manager_compaction.py drops
`test_plan_state_of_this_repository_plan`.
Depends on: none
Risk: standard — read-only script; the transcript format is undocumented, so fail soft.
Acceptance: the script runs on a synthetic transcript fixture in tests and on this repository's
real transcripts when present; run-record columns documented; no write outside the run-record file.
Validation: standard; plus the new script folder's `unittest discover`.
Notes: measured facts in docs/TODO.md items 4 and 11.

### P4. Watch the orchestrator's context
Status: todo
Objective: the orchestrator learns when its own context is large before it pays for it.
Scope: a PostToolUse hook on `Agent` (plugins/manager-plugin/hooks) that reads the last request's
usage from the hook input's `transcript_path` (reuse P3's reader) and, above a budget (default
200,000 tokens; `.codemap.json`-independent; documented), prints one `additionalContext` line: write
the working-notes lines, then suggest `/compact` to the owner at the next stop; only during a
manager run (P2's marker); fail open; fast. Also: usage.py bounds the orchestrator line to the run
(e.g. `--since`) and resume counts leave out (or document) requests started by a long tool call;
run-record.md and the manager-retro skill follow.
Depends on: P2, P3
Risk: standard — advisory hook.
Acceptance: tested below/above budget, outside a run, missing transcript; under 50 ms on the common
path.
Validation: standard; plus P3's script folder `unittest discover`.
Notes: P4's hook reads only the transcript's tail (a last-request helper beside usage.py's `read`),
since `read` parses the whole transcript (~48–77 ms on 10–15 MB files).

### P5. Plan validation and phase extraction
Status: todo
Objective: a script checks a living plan and prints one phase's brief section.
Scope: plugins/manager-plugin/skills/living-plan/scripts/plan.py (+ tests): `check` (unique phase
ids, every `Depends on` resolves, no cycle, each phase has Status/Objective/Scope/Depends
on/Risk/Acceptance/Validation, scope overlap warning for phases with no dependency between them)
and `phase <id>` (the phase section plus the constraints, binding decisions, Phases preamble, open
decisions and model-strategy record). `phase` reads the plan from stdin
(`git show <base-sha>:<plan-path> | <python> plan.py phase <id>`), never a working-tree path, so the
plan-at-base read stays. The briefs and the orchestrator's step-0 phase read use it instead of the
awk command (keep the awk as the no-Python fallback); living-plan SKILL.md runs `check` before a
plan PR.
Depends on: P1, P2
Risk: standard — new script; briefs change one line each.
Acceptance: tests on the template shape, this plan and a malformed plan; the briefs' fallback kept;
`phase` has no path argument.
Notes: B1 (plan-at-base read).
Validation: standard; plus
`python3 -m unittest discover -s plugins/manager-plugin/skills/living-plan/scripts`.

### P6. Code-map "changed" command for reviewers
Status: todo
Objective: reviewers get a capped pointer list of what a diff touches.
Scope: codemap.py `changed --base <sha> --head <sha>` (changed files, top-level definitions touched,
files importing them, matching tests, vault pages mentioning them; output capped, e.g. 60 lines,
with a count of what was cut); reviewer-brief.md: run it when a Code map command is set, as
pointers only, never a filter; code-map SKILL.md documents it.
Depends on: P1, P2
Risk: standard — read-only command.
Acceptance: tests on a temp repo; output cap respected; works from a subfolder with `--root`.
Validation: standard.

### P7. Eval cases for the invariants
Status: todo
Objective: regressions in the plugin's invariants are caught by eval cases.
Scope: plugin eval cases (verify the installed CLI's `claude plugin eval` format and the plugin
manifest key first) for: no general-purpose spawn when a plugin agent fits; a reviewer after every
implementer round; merge pinned to the reviewed SHA; brake at the fix-round limit; no Edit/Write by
the orchestrator in a manager run. Also README.md and the folder of its schema test. Authoring and
a format check only; running them is a paid session and is out of this phase (document the command).
Depends on: P2, P3, P4, P5, P6
Risk: standard — new files; no behaviour change.
Acceptance: the cases pass the CLI's validation (or, if the CLI has no offline check, a test parses
them against the documented schema); README documents how to run them.
Validation: standard.

### P8. Docs and version 0.9.0
Status: todo
Objective: documentation matches 0.9.0.
Scope: README.md, docs/TODO.md (Done entry), .claude-plugin/marketplace.json description if it
changes, plugins/manager-plugin/.claude-plugin/plugin.json (0.9.0).
Depends on: P1, P2, P3, P4, P5, P6, P7
Risk: standard — docs.
Acceptance: no stale description of anything 0.9.0 changed; version 0.9.0.
Validation: standard.

## Change log
- 2026-11-20: plan created from two independent audits and a research report on 0.8.x.
- 2026-11-21: plan review notes folded in (P1 test scope, size ceilings vs later phases, P5 reads
  the plan from stdin at base).
- 2026-11-21: plan review notes folded in (P5/P6 depend on P2; ceiling rule in Constraints; P1 and
  P7 scopes; script test folders join standard validation)
- 2026-11-21: P3 also carries two P2 review notes (final-report bookkeeping pointer; a redundant
  plan-shape test removed)
- 2026-11-21: P3's script is plugins/manager-plugin/skills/manager/scripts/usage.py (`read(paths)`
  is the reader P4 reuses) and its folder's `unittest discover` joins the Validation line; it
  counts a resume as cold when under half of the previous prompt was read from the cache, since an
  expired cache still reads a shared prefix
- 2026-11-21: P4 reads only the transcript's tail, with a last-request helper beside P3's `read`,
  which parses the whole transcript (~48–77 ms on 10–15 MB files)
- 2026-11-21: P4 also carries two P3 review notes (per-run orchestrator usage; tool waits in resume
  counts)
- 2026-11-21: P4's hook is plugins/manager-plugin/hooks/manager-context-watch.sh (PostToolUse on
  `Agent|Task`; its logic is skills/manager/scripts/context_watch.py, with usage.py's `last`); the
  environment variable `MANAGER_CONTEXT_BUDGET` sets the budget; usage.py's `--since` takes the
  run marker file (its modification time) or an ISO 8601 time; a subagent's resume counts leave
  out the requests a tool result started, the orchestrator's keep them

## How to keep this plan alive
- A phase PR updates its own status line and links itself; other status lines only to correct facts.
- Facts that change later phases → update those phases in the same PR and add a change-log line.
- Decision, binding-decision and model-strategy records change only as the manager's Plan records
  say.
- Never copy SHAs or test output into the plan beyond a PR link.
