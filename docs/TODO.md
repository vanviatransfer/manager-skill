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

### 7. Large saved auto-compact windows (plugin 0.7.4)

- An owner saw new manager sessions still running with a 600k auto-compact window. `/autocompact`
  saves its value per model in the user settings, so a window set on an older plugin version's
  advice stays in place, and the session check treated any value already set as the owner's
  choice and said nothing. The session check now also recommends `/autocompact 300k` when the
  saved value is above 300k, naming the current value; a value of 300k or less is still left alone,
  and the manager never changes a setting itself.

### 8. Code map kept current, vault and rules block set up together (plugin 0.8.0)

- A project repository's map went stale: a session outside a manager phase added scripts and vault
  notes over several PRs without running `build`, and nothing else guards the map.
- Two opt-in commit hooks, both off by default. A git pre-commit hook, per clone (`codemap.py
  install-hook` / `uninstall-hook`): when staged changes touch the map's inputs it runs `build`
  and stages only the map pages; it stops the commit when an input has unstaged changes or the
  build refuses, chains an existing hook (run first, restored on uninstall) and writes nothing
  inside the work tree under `core.hooksPath`. A Claude Code `PreToolUse` hook on Bash, versioned
  (`"commit_check": true` in `.codemap.json`): before a `git commit` it runs `check --quiet` and
  blocks while the map is stale. It runs only at commit time, not after every edit, and also covers
  fresh clones and cloud sessions where `.git/hooks` is empty.
- `check --quiet` first compares a fingerprint of the inputs (tracked paths, blob ids of the files
  whose content the map reads, the config, the format, the script) stored on the map page; when it
  can't decide, it runs the full check, so it never calls a stale map current. Measured once on a
  synthetic repository (230 source files in four languages, 251 vault pages with links, 4 CPUs,
  three runs): `build` 0.08–0.09 s, full `check` 0.07 s, `check --quiet` on a fingerprint hit
  0.05 s, a commit touching no inputs 0.14–0.16 s with the hook (0.09 s without), a vault-page
  commit with the hook 0.19–0.20 s, the Claude Code hook 0.06 s on a commit and under 0.01 s on
  other commands. Small files; larger ones widen the gap between the full and the quick check.
- Sessions didn't use the map unless told: `codemap.py rules-hint` adds a short marked block to
  `AGENTS.md` and `CLAUDE.md` (read the vault index and `query` before broad searches, rebuild
  after changes, use the plugin's restricted agents instead of `general-purpose`), by skill name,
  never a script path; idempotent, nothing else in the files changes.
- Vault, map and rules block now come together: `create-vault` sets up the map and the block in
  its own PR, the `code-map` skill creates a vault first when there is none, and the manager makes
  sure a repository has all three in one setup PR before the first phase. A missing vault is the
  one thing it asks about (yes / not this time / never in this repo); the hooks are a separate yes.
  A vault costs the same whether `create-vault` is run by hand or by the manager; the manager only
  moves it to the first run. For a short-lived or tiny repository the owner can decline it (a
  Decided entry or a project rule), and the manager honours that.
- Fingerprint trade-off (design choice): the map page's last line changes with every input change,
  so with `commit_check` on, parallel branches conflict on it more often; the rule is unchanged
  (run `build` again after resolving the inputs).
