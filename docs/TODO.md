# Open ideas

## Done

### 1. `/autocompact` before a run (plugin 0.5.2; 200–300k in 0.7.0, 300k since 0.7.1)

- Findings (Claude Code docs, model-config / settings / CLI reference): `/autocompact <tokens|auto>`
  sets the window at which the main session auto-compacts (100000–1000000, `250k` style accepted),
  saved per model in user settings; also settable by `autoCompactWindow` /
  `modelSettings.<model>.autoCompactWindow` in settings files, `claude --autocompact`, or
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Claude Code caps it at the model's context window.
- A skill can't run a built-in command, and editing the owner's settings silently would overstep,
  so the manager checks the value read-only in step 0 and, when none is set, recommends
  `/autocompact 300k` in the model-strategy question (or the final report). A value the owner set
  is left alone. It covers the main session only.
- 0.5.2 recommended a much larger window; 0.7.0 lowered it, since a thin orchestrator should carry
  little context per turn. Expected effect (inferred, not measured): earlier compaction and fewer
  tokens per orchestrator turn on long runs. 0.7.1 settled on 300k: it equals the implementer and
  worker cap (below 300k the orchestrator's window lowers theirs), and the Pricing page bills
  Claude 4.6 and later models except Haiku 5.5 at the standard rate across the full 1M window
  (checked 2026-11-16), so nothing argues for staying at or under 200k.

### 2. `cc-plugin-you-should-know` — not added

- Built-in mod (Claude Code 2.1.287+), off by default. While on, a side agent rereads the
  conversation now and then in a separate request to the same model and shows a note above the
  prompt for the user to answer.
- For manager runs it adds requests during long tasks and shows notes meant for a person at the
  prompt, who usually isn't watching an autonomous run. No documented way for another plugin to
  depend on it.
- Decision: don't include it; the manager's step-0 check recommends disabling it when it is enabled.

### 3. Self-improving loop (plugin 0.6.0)

- Run records in ~/.claude/manager-runs/ on the owner's machine (numbers and generic tags only), a
  proposed binding decision when a blocker class recurs in a run, and the `manager-retro` skill that
  turns measured patterns into at most three owner-chosen, independently reviewed changes.
- Expected effect (to be measured by the records themselves): fewer repeated fix rounds per project,
  and skill changes backed by numbers rather than single-run impressions.

### 4. Token economy (plugin 0.7.0)

- The manager skill and both briefs are at least 25% shorter in words; rare sections live in
  `skills/manager/references/` and are read when their trigger applies.
- Loop rules: fix-round limit 5 by default (approach question at round 3); implementer rotation
  after 3 resumed rounds or about 400k cumulative `subagent_tokens`, with a `Handoff:` note instead
  of a transcript; series mode for up to 3 independent, same-shape `standard` phases on one
  implementer, each PR still reviewed and landed on its own exact-SHA verdict; a short implementer
  return with the full report in a file.
- Agent caps: `autoCompactWindow` (300000 implementer and worker, 200000 the others) and
  `maxTurns` (500 / 300). The window is a ceiling over the parent's; `maxTurns` is per run, so a
  resume gets a fresh budget.
- Measured inputs (small samples): restricted agents start at about 9–14k tokens,
  general-purpose about 77k; a phase's implementer median is about 207k (Sonnet) / 353k (Opus).
  The thresholds (25%, 3 rounds, about 400k, 3-phase series, the windows) are design choices; the
  run records should show whether they lower tokens per landed phase. The caps' effect is
  unmeasured.

### 5. Live-test fixes (plugin 0.7.2)

- From a live run on a scratch test repository:
  1. Stale candidate: loop step 2 checks that the candidate contains the current default head and
     integrates first (as 4a step 3, counting toward the fix-round limit), so a review isn't spent
     on a stale candidate; 4a step 3 stays the last check before landing.
  2. Generated files: implementers stage by path (never `git add -A` / `git add .`), commit no
     caches or build output unless the scope names them, and validate without writing them into
     the tree where the toolchain allows.
  3. Single-branch clones: `git fetch origin <branch>` creates no `origin/<branch>` ref, so
     branches are fetched with an explicit refspec (`github-backends.md`, **Fetching a branch**)
     or compared by SHA; every fetch in the skill and briefs points there.
  4. Validation leftovers: the reviewer deletes and lists the untracked files its run created; the
     orchestrator removes any still present, each by its listed path.
  5. README: the full-1M-window standard rate is qualified as Claude 4.6 and later Opus and Sonnet
     models.
  6. Language: the living plan and the vault are written in English, whatever language a
     project's other docs use (owner decision, 2026-11-16); talking to the owner stays in the
     owner's language.

### 6. Separate round counters (plugin 0.7.3)

- From a live rotation test on a scratch test repository: a phase with zero defects reached fix
  round 5 and rotated only because the default branch moved four times (each integration round
  cost about 2k tokens; the rotation cost a fresh start of about 22k). Owner-approved, 2026-11-16:
  1. Separate counters: the fix-round brake, the approach question and rotation count only rounds
     after a CHANGES REQUIRED review. Integration rounds (loop step 2 and 4a step 3) have their own
     limit, at most 5 per phase (a plan or project limit on review attempts still wins); a 6th
     needed blocks the phase as "default branch moving faster than the phase can land". The
     review-ledger marks integration rounds `INTEGRATE`, so both counts come from it.
  2. Rotation by tokens: a fresh implementer once the current one's cumulative `subagent_tokens`
     reach about 400k, or after 3 of its fix rounds once they are above about 150k (design
     choices). Integration rounds never trigger rotation by count.
  3. Language during a run: new or changed plan and vault text the implementers write is in
     English, owner quotes stay verbatim, and unchanged text is not translated unless the phase
     says so; project rules still win.
