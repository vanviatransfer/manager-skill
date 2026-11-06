# Open ideas

## Done

### 1. `/autocompact 600000` before a run (plugin 0.5.2)

- Findings (Claude Code docs, model-config / settings / CLI reference): `/autocompact <tokens|auto>`
  sets the window at which the main session auto-compacts (100000–1000000, `600k` style accepted),
  saved per model in user settings; also settable by `autoCompactWindow` /
  `modelSettings.<model>.autoCompactWindow` in settings files, `claude --autocompact`, or
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Claude Code caps it at the model's context window.
- A skill can't run a built-in command, and editing the owner's settings silently would overstep,
  so the manager checks the value read-only in step 0 and recommends `/autocompact 600k` in the
  model-strategy question (or the final report).
- Effect: on a 1M-token model 600k compacts earlier than the default, so long runs carry less
  context per turn at the cost of an occasional extra compaction; on a 200k model it is a no-op.

### 2. `cc-plugin-you-should-know` — not added

- Built-in mod (Claude Code 2.1.287+), off by default. While on, a side agent rereads the
  conversation now and then in a separate request to the same model and shows a note above the
  prompt for the user to answer.
- For manager runs it only adds cost: extra model requests during long tasks, notes meant for a
  human who isn't watching an autonomous run. No documented way for another plugin to depend on it.
- Decision: don't include it; the manager's step-0 check recommends disabling it when it is enabled.
