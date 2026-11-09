# Open ideas

## Done

### 3. Self-improving loop (plugin 0.6.0)

- Run records in the plugin's local data directory (numbers and generic tags only), a proposed
  binding decision when a blocker class recurs in a run, and the `manager-retro` skill that turns
  measured patterns into at most three owner-chosen, independently reviewed changes.
- Expected effect (to be measured by the records themselves): fewer repeated fix rounds per project,
  and skill changes backed by numbers rather than single-run impressions.

### 1. `/autocompact 600000` before a run (plugin 0.5.2)

- Findings (Claude Code docs, model-config / settings / CLI reference): `/autocompact <tokens|auto>`
  sets the window at which the main session auto-compacts (100000–1000000, `600k` style accepted),
  saved per model in user settings; also settable by `autoCompactWindow` /
  `modelSettings.<model>.autoCompactWindow` in settings files, `claude --autocompact`, or
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Claude Code caps it at the model's context window.
- A skill can't run a built-in command, and editing the owner's settings silently would overstep,
  so the manager checks the value read-only in step 0 and recommends `/autocompact 600k` in the
  model-strategy question (or the final report).
- Expected effect (inferred, not measured): on a model whose default window is larger than 600k,
  compaction can come earlier, so long runs may carry less context per turn; the cap at the model's
  context window applies.

### 2. `cc-plugin-you-should-know` — not added

- Built-in mod (Claude Code 2.1.287+), off by default. While on, a side agent rereads the
  conversation now and then in a separate request to the same model and shows a note above the
  prompt for the user to answer.
- For manager runs it adds requests during long tasks and shows notes meant for a person at the
  prompt, who usually isn't watching an autonomous run. No documented way for another plugin to
  depend on it.
- Decision: don't include it; the manager's step-0 check recommends disabling it when it is enabled.
