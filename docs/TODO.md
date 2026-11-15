# Open ideas

## Done

### 1. `/autocompact` before a run (plugin 0.5.2; 200–300k since 0.7.0)

- Findings (Claude Code docs, model-config / settings / CLI reference): `/autocompact <tokens|auto>`
  sets the window at which the main session auto-compacts (100000–1000000, `250k` style accepted),
  saved per model in user settings; also settable by `autoCompactWindow` /
  `modelSettings.<model>.autoCompactWindow` in settings files, `claude --autocompact`, or
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Claude Code caps it at the model's context window.
- A skill can't run a built-in command, and editing the owner's settings silently would overstep,
  so the manager checks the value read-only in step 0 and, when none is set, recommends
  `/autocompact 250k` (an orchestrator window of 200–300k) in the model-strategy question (or the
  final report). A value the owner set is left alone. It covers the main session only.
- 0.5.2 recommended a much larger window; 0.7.0 lowered it, since a thin orchestrator should carry
  little context per turn. Expected effect (inferred, not measured): earlier compaction and fewer
  tokens per orchestrator turn on long runs.

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
