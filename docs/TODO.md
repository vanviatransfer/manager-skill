# Open ideas

## Watching

### Claude Code Code Mode (experimental) — not adopted yet

- What it is: an opt-in Claude Code feature (2.1.323+, `CLAUDE_CODE_EXPERIMENTAL_CODE_MODE=1`)
  where the model writes a JavaScript script that chains several Bash/Read/Edit calls in one step
  (parallel commands, one result fed into the next, only the needed output returned).
- Why it may matter here: fewer round trips and less intermediate tool output in context, the
  same goal as the code map and the restricted agents.
- Why not now: [claimed] experimental and may change or be removed in any release; not available
  in the Desktop app, the VS Code panel, cloud sessions or `-p`; no published token or latency
  figures. [claimed] Each tool call inside a script still goes through permission rules and
  PreToolUse hooks; [not measured] whether this plugin's hooks (general-purpose block, search
  nudge, commit check) fire inside a Code Mode script.
- Revisit when it leaves experimental or reaches the Desktop app. First step then: one CLI
  session, no manager run, a small task, and check that the plugin's hooks still fire; then
  measure context use against the same task without it.
- Sources: InfoQ and MarkTechPost coverage (November 2026); check the official Claude Code docs
  before acting.

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
  after 3 resumed rounds or about 400k cumulative `subagent_tokens` (superseded in 0.8.3, item 11:
  the figure is a context size and rotation follows the prompt cache), with a `Handoff:` note
  instead of a transcript; series mode for up to 3 independent, same-shape `standard` phases on one
  implementer, each PR still reviewed and landed on its own exact-SHA verdict; a short implementer
  return with the full report in a file.
- Agent caps: `autoCompactWindow` (300000 implementer and worker, 200000 the others; fallback
  300000 since 0.8.3) and `maxTurns` (500 / 300). The window is a ceiling over the parent's;
  `maxTurns` is per run, so a resume gets a fresh budget.
- Measured inputs (small samples): restricted agents start at about 9–14k tokens,
  general-purpose about 77k; a phase's implementer median is about 207k (Sonnet) / 353k (Opus).
  The thresholds (25%, 3 rounds, about 400k, 3-phase series, the windows) are design choices; the
  run records should show whether they lower tokens per landed phase. The caps' effect is
  unmeasured.

### 5. Live-test fixes (plugin 0.7.2)

- From a live run on a scratch test repository:
  1. Stale candidate: loop step 2 checks that the candidate contains the current default head and
     integrates first (as 4a step 3; it counted toward the fix-round limit until 0.7.3 gave
     integration rounds their own, item 6), so a review isn't spent on a stale candidate; 4a
     step 3 stays the last check before landing.
  2. Generated files: implementers stage by path (never `git add -A` / `git add .`), commit no
     caches or build output unless the scope names them, and validate without writing them into
     the tree where the toolchain allows.
  3. Single-branch clones: `git fetch origin <branch>` creates no `origin/<branch>` ref, so
     branches are fetched with an explicit refspec (`github-backends.md`, **Fetching a branch**)
     or compared by SHA; every fetch in the skill and briefs points there (since 0.8.3 the two
     briefs give the command itself).
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
     choices). Integration rounds never trigger rotation by count. (Superseded in 0.8.3, item 11.)
  3. Language during a run: new or changed plan and vault text the implementers write is in
     English, owner quotes stay verbatim, and unchanged text is not translated unless the phase
     says so; project rules still win. (Since 0.8.3 English wins over a project rule that names
     another language for plan or vault text, item 11.)

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
  build refuses, chains an existing hook (run first, restored on uninstall), writes nothing inside
  the work tree under `core.hooksPath`, and uses a shared `core.hooksPath` folder outside the
  repository only with `--shared`. A Claude Code `PreToolUse` hook on Bash, versioned
  (`"commit_check": true` in `.codemap.json`): before a `git commit` it runs `check --quiet` and
  blocks while the map is stale. It runs only at commit time, not after every edit, and also covers
  fresh clones and cloud sessions where `.git/hooks` is empty. It does nothing when it can't tell
  which repository commits (`cd`, `git -C`, a script); those are documented gaps.
- `check --quiet` is the full check with one line of output or none. A fingerprint fast path
  (a hash of the inputs on the map page) was tried and removed: review found a soundness hole in
  three rounds (index flags, a lossy clean filter, `"`-quoted paths, a linked file untracked) for
  a gain of 0.05–0.1 s; the tests keep all four repros, each checking `check --quiet` agrees with
  `check`. The git hook compares the raw bytes of every staged input with its blob (`git
  hash-object --no-filters`, paths as arguments) and refuses on a difference other than CRLF,
  or when a tracked input isn't a readable file there (sparse checkout, skip-worktree, deleted).
  Measured on a synthetic repository (230 source files in four languages, 251 vault pages with
  links, 4 CPUs, three runs): `build` 0.07–0.09 s, `check` and `check --quiet` 0.07 s, the Claude
  Code hook 0.08–0.09 s on a commit and under 0.01 s on other commands, a commit touching no
  inputs 0.14–0.19 s with the git hook (0.08–0.11 s without), a vault-page commit with the hook
  0.20–0.22 s. With files ten times larger (4 MB): `build` 0.17–0.22 s, `check` and `check
  --quiet` 0.16–0.17 s, the Claude Code hook 0.17–0.21 s, a vault-page commit with the hook
  0.29–0.30 s.
- Behaviour changes for repositories that don't opt in, both harmless: `build` leaves a map page
  whose content is unchanged untouched (no rewrite, same mtime), and `build --redetect` keeps
  extra `.codemap.json` keys (such as `commit_check`) instead of dropping them.
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

### 9. Map first: a nudge before the first broad search (plugin 0.8.1)

- In repositories with a code map, sessions still began with broad grep and glob exploration;
  the rules block that says to use `query` and the vault index first is only advice.
- A `PreToolUse` hook on Grep, Glob and Bash (`codemap-search-nudge.sh`, logic in
  `search_nudge.py`), on by default wherever `.codemap.json` has a `map`, off with
  `"search_nudge": false`. It blocks the first broad search of a session once with one line
  (`query` or the vault index first, then repeat the search) and allows every later one; a
  `codemap.py query` or `mentions` run first means no block. Each subagent gets its own nudge
  (key: `session_id`, `agent_id`, `transcript_path`, repository top folder). State is a marker
  file in the OS temp folder, never in the repository; any error allows the search.
- Broad: the repository root or a top-level folder (no path = the working directory), a Glob
  reaching `**` from there, `grep` only with `-r`. Narrow: files, paths two or more levels deep,
  the vault and the map pages. When unsure it allows; the gaps are in the `code-map` skill.
- Measured (4 CPUs, 20 runs, median): a Bash command without a search word 4 ms (no Python
  started), one that reaches Python but isn't a search 23–24 ms, Grep in a repository without a map
  23–24 ms, the first broad Grep in a mapped repository 30–31 ms (blocked), a later Grep 30 ms.

### 10. Map first, runnable by every agent (plugin 0.8.2)

- The plugin's agents have no Skill tool, so a nudge saying "run the `code-map` skill's `query`"
  left them repeating the search. The `sh` wrapper now passes the Python it found and the plugin
  folder (`CLAUDE_PLUGIN_ROOT`, else its own absolute path) to `search_nudge.py`, and the one-line
  message names the command: `<python> "<plugin>/skills/code-map/scripts/codemap.py" query
  <term> --root "<repo top>"` (double-quoted, forward slashes on Windows; without `--root` when
  the top folder's path holds a control character). When the script can't be found there, the
  message keeps the 0.8.1 wording.
- The implementer and reviewer briefs say to run `<code map> query <term>` (and read the vault
  index) before any broad search; the worker, researcher and fallback agents run a command a hook
  names before searching again; the rules block tells agents without the Skill tool that the hook
  prints the exact command (still no path in the block).
- Measured (4 CPUs, 20 runs, median): the first broad Grep in a mapped repository 28 ms (blocked,
  with the command), a later Grep 27 ms.

### 11. Rotation by the prompt cache, section-only plan reads, versioned rules block (plugin 0.8.3)

From an independent audit and a research report of the plugin; every item owner-approved
(2026-11-20). Evidence tags: **[measured]** from the transcripts of one long session (its main
conversation and its subagents; read-only, numbers only, standard-library Python run with `-I`),
**[docs]** as the documentation says (checked 2026-11-20), **[inferred]** computed or concluded
from those. The session was still running, so each count is as of its measurement.

- **`subagent_tokens` is a context size.** [measured] In 36 of 36 Agent results the figure equals
  the subagent's last request (input + cache write + cache read + output) and in none the sum over
  its requests (1.2–5.5 times larger in 12 samples). [inferred] 0.7.0 and 0.7.3 (items 4 and 6)
  read it as cumulative usage; under a 300k compaction cap their "about 400k" trigger could
  hardly fire. The skill, the run record (columns renamed `impl context` / `review context per
  round`; older records hold the same figures under the old names), `manager-retro`, the README
  and the living plan now say what it is.
- **Cache lifetimes.** [docs] Claude Code requests a 1-hour cache for the main conversation on a
  subscription within plan usage and 5 minutes for everything else, subagents included; 5 minutes
  for both on an API key, usage credits or a cloud provider (`promptCacheTtl`,
  `subagentPromptCacheTtl` and an agent's `experimental.cacheTtl` change this). The lifetime
  restarts at each use; after it the whole prefix is written again, however long the pause was
  (code.claude.com/docs/en/prompt-caching). [measured] Subagents: 1,905 requests wrote 6,755,029
  tokens to the 5-minute cache and none to the 1-hour one; the main conversation: 762 requests,
  none and 7,072,815. All 14 subagent requests sent 123–294 s after the previous one (5 more
  that followed a compaction left out) read their previous context from the cache to within
  2.3k tokens; all 4 sent after 323–454 s read nothing and wrote their whole context again (75k,
  105k, 225k, 194k tokens). In the main conversation 34 requests after pauses of 240–1,543 s
  read at least 98% from the cache and 12 after 4,740 s or more wrote the context again (no
  sample between 26 and 79 minutes).
- **Prices.** [docs] Against the base input price: a 5-minute cache write 1.25, a 1-hour write 2,
  a cache read 0.05 on the current Opus and Sonnet models (0.1 on most others), output 5
  (platform.claude.com/docs/en/build-with-claude/prompt-caching and .../about-claude/pricing).
- **A fresh implementer's start.** [measured] 12 finished implementers (6 on a tiny scratch
  repository, 6 on a real one; none was ever resumed): first prompt 8,794–9,577 tokens (median
  9,000); context at the first call that changes something (`F`) 17,169–64,119, median 36,070
  (17–22k on the scratch repository, 50–64k on the real one), reached after a median of 7
  requests that together wrote 28,631 tokens to the cache, read 186,727 from it and produced
  3,617 of output (medians). Context at the last return 21,835–158,396. [inferred] At the prices
  above that start costs 19,920–165,174 base-input-token equivalents, median 61,787 (71,485
  with reads at 0.1).
- **Break-even.** [inferred] Model for a round of `N` requests, read price `r`, start cost `S`:
  a resume whose cache has expired costs about `1.25·C + r·C·(N−1)` for a context of `C`, a warm
  resume `r·C·N`, a fresh implementer `S + r·F·N` (the round's own growth is the same for all
  three and left out). The context above which a fresh implementer is cheaper, median over the
  12 (range):

  | `N` | cold, `r` 0.05 | cold, `r` 0.1 | warm, `r` 0.05 |
  | --- | --- | --- | --- |
  | 5 | 48,664 (16,919–124,968) | 53,962 (18,547–136,431) | 282,256 (98,131–724,817) |
  | 10 | 46,670 (17,144–116,020) | 49,577 (18,525–118,276) | 158,680 (58,291–394,468) |
  | 20 | 44,042 (17,441–104,224) | 44,982 (18,501–99,256) | 96,892 (38,371–229,293) |
  | 30 | 42,387 (17,628–96,797) | 42,656 (18,324–90,162) | 76,296 (31,731–174,235) |

  The cold break-even follows the repository: medians 21–25k for the six on the scratch
  repository, 85–121k for the six on the real one (`r` 0.05: 110,712 / 102,586 / 91,875 / 85,131
  for `N` 5 / 10 / 20 / 30; `r` 0.1: 120,299 / 105,220 / 89,422 / 81,238); it is 0.9–2.4 times
  `F` (median 1.25–1.5). One fixed number for every repository, scored on the 12 (each one's
  last context as the resumed context, its own start as the alternative; extra cost over the
  cheaper choice, summed, in thousands of base-input-token equivalents, for `N` 5 / 10 / 20):

  | cold: fresh above | `r` 0.05 | `r` 0.1 |
  | --- | --- | --- |
  | always | 237 / 212 / 163 | 353 / 303 / 224 |
  | 50k | 284 / 272 / 249 | 389 / 365 / 338 |
  | 75k | 111 / 106 / 97 | 137 / 127 / 127 |
  | 100k | 82 / 84 / 88 | 88 / 90 / 116 |
  | 125k or 150k | 52 / 63 / 87 | 45 / 68 / 134 |
  | never | 146 / 182 / 254 | 141 / 212 / 375 |

- **The rule (manager skill, Rotation).** At a round boundary a fresh implementer takes over when
  the current one's context is about 150k or more (the warm break-even for a round of about 10
  requests, and the owner's cap), or above about 100k when its last return is more than 5 minutes
  old or untimed (cold: 100k is within the real repository's break-even range and near the low
  end of the table above for both read prices); otherwise the same implementer is resumed. Cold,
  the Handoff request is skipped, since asking for the note would itself re-write the context:
  the `Fix round` field, the PR and git are the state. The 400k and round-count triggers are
  gone. Limits: 12 implementers, one session, two repositories, only two contexts above 100k and
  no resumed round measured, so `N` for a fix round is a guess; 100k against 125–150k is within
  the sample's noise. Small repositories would rotate earlier at their own break-even (about
  1.3 times `F`), which the orchestrator can't see. Not taken: `experimental.cacheTtl: 1h` on the
  implementer (writes at 2 instead of 1.25; ignored on usage credits).
- **Idle compaction.** [docs] Claude Code has one: `idleCompaction` (on by default, 2.1.290 or
  later) compacts a conversation left idle for about an hour, before the cache expires, when the
  session is a local interactive one (terminal, the VS Code panel, the desktop app's Code tab on
  the machine or over SSH), auto-compact is on, the conversation is on the 1-hour cache and its
  context has reached 200,000 tokens (`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`, at least 100000);
  the computer must stay awake (code.claude.com/docs/en/settings-reference). It doesn't cover
  cloud sessions, smaller contexts, or the 5-minute cache. No hook, skill or model can run
  `/compact`, and nothing else runs while a session is idle; a `/compact` after the cache has
  expired re-reads the history uncached (prompt-caching page). So the manager only adds a line
  when it stops to wait for the owner: answering after more than about 50 minutes → run
  `/compact` now, or answer in a new session. The gate also recommends a new session when the
  conversation already holds unrelated work (no handoff note: step 0 rebuilds the state).
- **Section-only plan reads.** Both briefs read the plan through one `git show ... | awk`
  command that prints the constraints, the binding decisions and the phase's own section; the
  reviewer reads the project rules at the base SHA too. [measured] On this repository's plan
  the command prints under half of the file's words for every phase (a test asserts it); the
  audit measured about 1,061 of 13,687 words for the largest phase of a large plan [claimed, not
  re-measured here]. (0.9.0: it also prints the `## Phases` preamble, with the status values and
  the fix-round limit, and the briefs say to `grep -n '^## '` when a plan names the constraints
  or binding-decisions section differently.)
- **Rules block version.** The block's begin marker carries a template version (`v2`; an
  unversioned block is version 1). A `SessionStart` hook prints one context line with the
  `rules-hint` command when a repository's block is older; `rules-hint` replaces it and leaves
  a higher version alone; the manager's setup PR updates an outdated block without asking.
  [measured] The hook takes 49–55 ms (4 CPUs, 20 runs, median) whether it prints or not.
  (0.9.0: an unversioned block whose text equals the template counts as current, so a
  repository set up by 0.8.2 pays no setup PR for the marker alone; the next `rules-hint` run
  writes the versioned marker. The hook's line is information, not an order: it names the
  command and says a manager run does this in its setup PR.)
- **Also.** Plan and vault text is English even where a project rule names another language
  (the owner's standing policy; reviewers don't flag it). All five agents set `omitClaudeMd`
  and read the working repository's rules themselves ([measured] the installed CLI's
  plugin-agent loader accepts the key; 0.9.0: both briefs get a `Project rules` dispatch field
  listing every rules file the repository has, `.claude/CLAUDE.md`, `.claude/rules/*.md` and
  `@path` imports included); the fallback agent's window is 300000. A reviewer's
  blocker cites its ground, and a review carries at most 3 notes, each with a consequence and an
  action. Effort: `medium`, a critical phase's reviewer `high`. The same-blockers brake offers
  the approach retries only with rounds left; an owner decision that unblocks a braked phase
  restarts its counts. The Fix round, Integrate and Handoff messages are in the skill; the
  ignored-data guard is POSIX `sh`; the short return has a `Risks:` line; a clean shared checkout
  ends the run on `origin/<default>`; the usage-percentage step is gone; waiting for a
  subagent's completion notification is the normal path.
- Done in 0.9.0 (item 12): the manager skill's size; hooks around compaction; an orchestrator
  context-size hook; real token accounting; a plan validate/extract script; a reviewer "changed"
  code-map command; plugin evals.

### 12. Compaction, real token accounting, plan and diff scripts, evals (plugin 0.9.0)

From two independent audits and a research report on 0.8.x, run as a living plan of eight
phases, one reviewed PR each. Evidence tags as in item 11; what is tagged [measured] here was
measured on 2026-11-21 on one Linux machine (4 CPUs), timings as the median of 20 runs.

- **0.8.3 follow-ups.** The session-start rules-version line is information, not an order, and
  an unversioned rules block with the template's text counts as current (both noted in item
  11). The brake-reset rule is stated once. The briefs' plan read also prints the `## Phases`
  preamble and says what to do when a plan names its sections differently. The implementer's
  dispatch gets a `Project rules` field like the reviewer's, listing every rules file the
  repository has (`CLAUDE.md`, `AGENTS.md`, `.claude/CLAUDE.md`, `.claude/rules/*.md` and their
  `@path` imports), since `omitClaudeMd` drops the whole instruction block. The final report
  reads a phase's report file only when its short return's `Risks:` line is not `none`; loop
  step 2's fact checks run in one Bash call. Self-training skill files, lessons and records are
  English, like plan and vault text.
- **A manager skill that fits after a compaction.** [docs] After a compaction Claude Code
  re-attaches the first 5,000 tokens of each invoked skill, within 25,000 tokens for all of
  them (code.claude.com/docs/en/skills, checked 2026-11-21). [measured] The manager skill had
  35,351 characters in 0.8.3 and has 17,997 now. The invariants and the loop's skeleton stay
  in it; step detail moved to seven new reference files (25 in all), each named in the skill
  with its trigger and read at its step and again after a compaction. Step 0 reads the plan's
  headings and every phase's `Status`, `Depends on` and `Risk` lines, not the phases' sections;
  a phase's section is read when the phase is scheduled. A test holds the ceilings: the manager
  skill 18,000 characters, the code-map skill 20,000, the implementer brief 1,327 words, the
  reviewer brief 1,347.
- **Compaction hooks.** The manager writes a run marker,
  `~/.claude/manager-runs/active/<session id>`, once the run's model strategy is settled and
  removes it when the run ends. While it exists, a `PreCompact` hook tells the summary to keep
  the working-notes lines verbatim, and a `SessionStart` hook (matcher `compact`) tells the
  session to re-read the skill and the references whose triggers apply. Both are one POSIX `sh`
  script without Python: silent without the marker, in a subagent and on any error; it writes
  nothing. [measured] About 5 ms a call, with or without the marker.
- **Real token accounting.** `skills/manager/scripts/usage.py` reads the session's transcript
  and its `subagents/agent-*.jsonl` and prints, for the orchestrator and per subagent: requests,
  uncached input, cache reads, cache writes by lifetime, output, context at return, warm and
  cold resumes, seconds. `--since` bounds the orchestrator's line to the run (the run marker's
  time). The run record gets these as `usage` lines and `manager-retro` measures them. A resume
  is a request sent 60 seconds or more after the previous one, cold when it read under half of
  the previous prompt from the cache; a subagent's counts leave out the requests a tool result
  started. The transcript format is undocumented, so what can't be read is skipped or
  `unknown`. Tested on synthetic transcripts; [measured] on one real session's transcripts it
  ended with exit status 0 and no `unknown` value.
- **Context watch.** A `PostToolUse` hook on the Agent tool reads, during a run, the
  orchestrator's last request from the transcript's end (its last 1 MiB) and, above 200,000
  tokens (`MANAGER_CONTEXT_BUDGET` sets another budget), adds one line: write the working-notes
  lines out now, suggest `/compact` to the owner at the next stop. [measured] With a 15 MiB
  synthetic transcript: 2 ms when the machine has no run marker (no Python started), 24 ms with
  only another session's marker, 28 ms in a run, over or under the budget.
- **Plan script.** `skills/living-plan/scripts/plan.py`: `check` (every phase id used once,
  every `Depends on` resolves, no cycle, the seven required lines of each phase; a warning when
  two phases, neither done and neither depending on the other, name the same path) and
  `phase <id>` (that phase's section with the constraints, the binding decisions, the
  `## Phases` preamble, the open owner decisions and the model-strategy record). Both read the
  plan from standard input and take no path, so the plan is still read as the base commit has
  it. The briefs and the orchestrator use `phase`, with the `awk` command kept as the
  no-Python fallback; the `living-plan` skill runs `check` before a plan's PR.
- **`changed` for reviewers.** `codemap.py changed --base <sha> --head <sha>` prints, per
  changed file (map pages left out), the top-level definitions whose text differs, its
  importers, its tests and the vault lines that mention it: at most 60 lines, then a count of
  the cut. The reviewer brief runs it for pointers only, never as a filter; the definitions are
  approximate (a change between two definitions names the one above).
- **Eval cases.** `plugins/manager-plugin/evals/` holds three cases for `claude plugin eval`:
  no general-purpose spawn when a plugin agent fits; a reviewer before a merge pinned to the
  reviewed SHA; the brake at the fix-round limit. The two manager cases also fail on any `Edit`
  or `Write` call. The CLI (2.1.329) has no offline check for cases, so a test parses them
  against its case format.
- **Not verified.** The three new hooks have not run inside a live session: the compaction
  hooks and the context watch are tested through their scripts with synthetic hook input, and
  no compaction of a manager run has been observed with them. The eval cases have not been run
  (paid sessions): a first run may need to adjust them, and it needs a shell sandbox, since
  the runner refuses a granted `Bash` it can't confine. No run of this version has been
  recorded yet, so there are no `usage` lines to measure and the rotation thresholds (item
  11) stand unchanged.
- Left out on purpose: delta-only re-review (it weakens review independence); a 1-hour cache
  for subagents (the plan records it as measured to cost more for reviewers and implementers;
  not re-measured here); dynamic workflows for the phase loop (large, and unverified with
  plugin agents).

### 13. Live-test fixes (plugin 0.9.1)

From a live test of 0.9.0 on 2026-11-21: nested Claude Code 2.1.330 sessions on one Linux
machine for the hooks, and the three eval cases run once each (`--model sonnet`).

- **Commit check: a `git add` that can run.** Its line always named the map page and the page
  folder; a one-page map has no folder, so the `git add` it led to failed ("pathspec ... did
  not match"). It now gives the `git add` command itself and names the folder only when the
  folder exists or the index holds pages of it. The check runs before the Bash command starts,
  so `build && git add ... && git commit` in one command was blocked every time: the line now
  says to run `build` and `git add` each as a command of its own.
- **Commit check: a rebuilt map left unstaged.** The check judged the working tree alone, so
  after `build` it let a commit through with the stale pages still in the index. It now also
  blocks while the index does not hold the map pages as the working tree has them (a changed
  or new page, a removed page the index still has; a page git ignores is left out) and names
  the `git add`. It still writes nothing. Known: `git commit -a`, and a `git add` chained in
  front of the commit, are blocked once in that state, as the line says.
  Two cases where that `git add` could not end the block are covered. A page under a clean
  filter that changes content (git-crypt, LFS, a filter of the repository's own), `ident` or
  `working-tree-encoding` never has the blob's bytes, so it counts as staged when `git add`
  would store the blob the index has (`git hash-object` with the filters: git runs the page's
  clean filter and writes no object; a filter that fails lets the commit pass). A page whose
  index entry is marked assume-unchanged or skip-worktree is passed by `git add`, so the line
  names `git update-index --no-assume-unchanged` / `--no-skip-worktree` first. Known (seen
  with git 2.43): in a sparse checkout whose rules leave the page out, `git add` still
  refuses after that, and its own message names `--sparse`.
- **The note on a leftover run marker.** The compaction line and the context line ended "(That
  run has ended: ignore this line and remove ...)". In a live session with a marker written by
  hand, the compaction's summary took that for a fact and wrote that no manager run was in
  progress. Both lines now state a condition: "(If no manager run is in progress any more,
  ignore this line and remove ...)". In that session all three manager-run hooks fired: the
  context line at a lowered budget, the `PreCompact` instructions, the `SessionStart` line
  after a manual `/compact`.
- **A resumed open PR reads its ledger.** The brakes count ledger lines, but the path of a new
  session that resumes an open PR (`establish-state.md`, item 5) never said to read the PR's
  review-ledger comments. In the eval run of `fix-round-brake` the orchestrator skipped that
  read and dispatched a sixth fix round as the first of five. The path now names the read, on
  both backends, ahead of the fresh review: the fix-round and integration counts and any
  `blocked` entry come from those comments, the rounds of earlier sessions included.
- **Eval graders that tell the orchestrator from a subagent.** The runner's `tool_used` grader
  counts the tool calls of every `assistant` event of a run, a subagent's too (read in the
  2.1.330 binary), so the manager cases' `no-edit` and `no-write` failed on an implementer's
  edits. They are now `regex` graders on the trace that match only a call of the orchestrator
  itself (an `assistant` event with `"parent_tool_use_id":null`); a third grader holds the same
  pattern to the reviewer dispatch, so a trace of another shape fails instead of passing those
  two for nothing. A test holds the pattern to synthetic events, and the three traces of the
  re-run agree with it (a subagent's `Write` is not matched).
- **Eval sandbox.** In these runs the shell could write nothing in the run's folder, which
  the runner made below `/tmp`, where its sandbox settings deny the shell writes: `git fetch`,
  `mkdir` and `touch` ended with "Read-only file system", while the `Write` tool wrote. So no
  commit, fetch or switch works in such a run. The fixtures leave the checkout on the PR's
  head with both branches fetched, so the path each case expects needs no write by the shell;
  the README says so.
- **Re-run with 0.9.1.** All three cases passed every grader (8, 8 and 4 of them), twice, one run
  per case each time: before the idle-compaction and retro-switch changes below (115 seconds, 0.68
  USD) and on the final text (130 seconds, 0.73 USD). Both times `fix-round-brake` read the ledger,
  reviewed the head, posted its ledger lines and blocked the phase without an implementer;
  `review-before-pinned-merge` reviewed, then merged pinned to the reviewed SHA;
  `plugin-agent-spawn` used a plugin agent. Two runs of a case are no pass rate.
- **Idle compaction: a recommendation at the gate.** Read again for 2.1.330.
  [docs] (code.claude.com/docs/en: `settings-reference`, `env-vars`, `hooks`, `prompt-caching`; read
  2026-11-21) `idleCompaction` is a Boolean, default `true`, in any settings file (2.1.290 on). It
  runs in an interactive terminal session, the VS Code panel and the desktop app's Code tab (on the
  machine or over SSH) when auto-compact is on (`DISABLE_AUTO_COMPACT` turns both off), the
  conversation is on the one-hour cache, the context has reached
  `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` (default 200000; a value below 100000 is raised to 100000)
  and "about an hour" has passed since the last request with the computer awake. Cloud sessions are
  not in that list. No setting for the delay is documented. `PreCompact` hooks with the `auto`
  matcher fire for it.
  [source] (the 2.1.330 binary) The timer is set at nine tenths of the cache's lifetime after the
  last request (54 minutes of an hour): a constant, with no setting or variable. It is armed only
  when the last main-thread request used the one-hour cache, and it gives up when the cache is no
  longer warm or the timer fires more than 60 seconds late, when the context is below the threshold
  (`max(100000, the variable or 200000)`), or when a newer request exists. In a cloud session
  (`CLAUDE_CODE_REMOTE`) one path depends on a server-side flag, so the binary doesn't settle
  whether it runs there. `CLAUDE_CODE_IDLE_THRESHOLD_MINUTES` and `CLAUDE_CODE_IDLE_TOKEN_THRESHOLD`
  belong to another feature (a hint to `/clear`), and `claude --help` has no idle option.
  [inferred] It fires before the cache expires, so the summary's request reads the cache; the delay
  can't be moved (to 50 minutes or anywhere); with the 300k window the plugin recommends, an
  orchestrator that waits between 100,000 and 200,000 tokens is covered only with the threshold at
  its minimum; the plugin's `PreCompact` hook has no matcher, so an idle compaction gets its
  instructions too.
  So `references/session-check.md` gains item (d): in a local session the manager recommends
  `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS=100000` in the `env` block of `~/.claude/settings.json`
  unless it is already that low, and says so when `idleCompaction: false` or `DISABLE_AUTO_COMPACT`
  keeps idle compaction off. The `/compact` line at a stop stays, for what idle compaction doesn't
  cover (a cloud session, a smaller context, a five-minute cache, a sleeping computer).
  [not measured] No idle compaction was observed (it takes an idle hour on a subscription's
  session): neither the 54 minutes nor the hooks firing on one was seen live, and whether one can
  start inside a long turn (a wait for a subagent) is not known.
- **Retro switch, off by default.** The run record is now opt-in, so someone who only runs plans
  pays nothing for the retro. `/manager-plugin:manager-retro on`, `off` and `status` run
  `skills/manager/scripts/retro.sh` (POSIX sh, so the switch needs no Python): `on` writes a flag
  file, `manager-plugin/retro` in the Claude config folder (`CLAUDE_CONFIG_DIR`, else `~/.claude`),
  `off` removes it, and `MANAGER_RETRO=on|off` in the environment overrides the file (a cloud
  environment, where the file doesn't persist). The manager runs the script once at step 0 (so after
  a compaction too): anything but `on` → no run record and no `usage.py`. The run marker is written
  as before, since the compaction hooks need it. Typed while off, `manager-retro` says so and how to
  turn it on, then goes on with the dated records already there (none: it stops), so turning
  recording off does not lock the records out of a retro. No record is ever deleted. After the
  update a machine that recorded runs stops recording until its owner types `on` once.
  [docs, source] `disable-model-invocation: true`, which the skill already had, holds for a plugin
  skill in 2.1.330: the skills page's table says "Description not in context, full skill loads when
  invoked", the plugin loader reads the key, the listing sent to the model leaves such skills out,
  and the Skill tool refuses one the user didn't type. So the skill costs other sessions nothing;
  its description, which the `/` menu shows, is shorter anyway.
  To stay under its 18,000 characters, the manager skill lost two summaries of what a reference
  holds (`review-round.md`, `final-report.md`: each file states its own contents). Tests: the script
  (default off, the file, `CLAUDE_CONFIG_DIR`, the variable, `on`/`off`, run records untouched) and
  the four texts that send to it. [not measured] No live manager run with the switch on.
- README: the context-watch hook and the record's `usage` lines need Python; without it the
  hook is silent and the record has no such lines.
- **Not verified.** No compaction of a real manager run has been observed with the hooks, and no run
  of this version is recorded. Of the four manager sessions of the two re-runs, one tried to write
  the run marker (the sandbox refused it, and it went on without it, as the rule says); none ran the
  retro switch's script or reached for a run record, so the switch is tested through its script and
  texts only, and its `on` path has not run live. The commit check's new block is tested through the
  script and the hook's shell wrapper, not inside a live session.

### 14. Retro switch read at step 0, git-lfs exception stated (plugin 0.9.2)

The two notes the review of 0.9.1 left, and two eval runs of one case on 2026-11-21 (Claude
Code 2.1.330, Linux, `--model sonnet`, switch off): one before and one after the fix that the
first led to.

- **The retro switch is read at step 0.** In 0.9.1 only the manager skill's **Run record**
  section named the switch's script, with "(step 0)"; step 0's own list did not, and
  `run-record.md`, which states the rule, is read only while the switch is on. No manager
  session of the 0.9.1 eval runs called the script: with the switch on, such a run would have
  kept no record and said nothing about it. Now item 1 of step 0 in the skill starts with the
  command, `sh "${CLAUDE_SKILL_DIR}/scripts/retro.sh"`. Item 1 of
  `references/establish-state.md`, read at every run start and again after a compaction, gives
  it as the first line of one Bash call whose other two lines are the reads that item already
  asked for (the plugin version, the reference files), and says what the line means: `on` → the
  run keeps a record, anything else → none. The **Run record** section no longer repeats the
  command, and its "(the default)" went: the skill is at 17,995 of its 18,000 characters, the
  ceiling unchanged.
- **The final report tells the cases apart.** It was "the run record path, or why it was skipped
  (retro switch off: neither)". Now, by the switch's line: `on` → the record's path, or that no
  record was written and why; `off` → nothing about a record; a switch never read in the run →
  the report says so.
- **An eval grader for the call.** `review-before-pinned-merge` gains `retro-switch-read`, a
  `regex` grader on the trace: a Bash call of the orchestrator itself (an `assistant` event with
  `"parent_tool_use_id":null`) whose command names `retro.sh`. Inside the call's input it passes
  over whole strings, so the script named in a description, a Read of it, a subagent's call and a
  quoted call do not count. A test holds the pattern to synthetic events with Python's `re`; on
  such events the pattern gave the same answers as a JavaScript regular expression (Node 22).
- **The first eval run, and the one fix it led to.** `review-before-pinned-merge` ran once (56
  seconds, 0.34 USD, 17 turns) on this change's first text: the call in item 1 of
  `establish-state.md`, and in the skill's step 0 only the words "check the retro switch". 8 of
  its 9 graders passed (the pinned merge, the review before it, no `Edit` or `Write` by the
  orchestrator, the outcome); `retro-switch-read` failed. The orchestrator never ran the
  script, and its final report said so: "I didn't read the plugin version or the retro switch,
  so there is no run record". That is the new final-report rule at work, and it shows that item
  1 of `establish-state.md` was not acted on at all (the version read stands there too), while
  the commands the skill itself gives inline (the fetch, the run marker) were run. The one fix
  made after that run: the command moved out of the **Run record** section into item 1 of
  step 0. The trace of that run was not kept, so what it read at step 0 is known only from its
  final report.
- **The second eval run, on the text after the fix.** The same case, once, with the same
  settings and the switch off, on the pull request's commit `ced669b`: exit 0, 50 seconds, 23
  turns, 0.31 USD, all 9 graders passed, `retro-switch-read` among them. Its trace was kept:
  the orchestrator's first Bash call, made before it read `establish-state.md`, runs the script
  ahead of the fetch in one command line, and the script printed `off (no flag file)`; the
  final report gives the switch as `off`.
  [not measured] How often the case passes: this is one run of the text after the fix.
  `fix-round-brake` and `plugin-agent-spawn` were not run on 0.9.2.
- **Open, seen in the passing run.** [not changed in 0.9.2] Only the first line of item 1's
  three-line call ran. The other two, the version read and the listing of the reference files,
  were not run by anyone in that run, although the orchestrator read `establish-state.md` right
  after its first call; so that run made no plugin-copy check. Its final report then gave a
  wrong reason for the missing version, that "the one command that would show it was denied":
  the only call that the run was denied was its last, a clean-up that reads no version.
- **A run with the switch on.** [not measured] No run-record line was seen to land. A case file
  can set only `EVAL_*` variables (read in the 2.1.330 binary: the runner refuses any other `env`
  key, which "must come from the operator's shell"), no run was started with `MANAGER_RETRO=on` in
  that shell, and in an eval run the shell can't write the record anyway (in these runs too: by
  the first one's final report the fetch and the run-marker write ended on a read-only file
  system, and the second one's trace shows the same for the fetch). So the `on` path is tested
  through the script, the texts and the step-0 call only. That call is run by a test with the
  skill's folder filled in, in a temporary home: `off` by default, `on` with the flag file, either
  one by the variable, the version line, the reference files, nothing written.
- **Commit check: the git-lfs exception.** Entry 13 says the check "still writes nothing" and
  that git "writes no object" when it runs a page's clean filter. That holds for git's own
  objects, not for a filter that stores what it cleans. Measured (git 2.43.0, git-lfs 3.4.1)
  with the map page LFS-tracked: the check on a rebuilt, unstaged page left one more object
  under `.git/lfs/objects` (1, then 2; a second check added none), the object that the `git add`
  it asks for stores anyway; the index and the working tree stayed as they were. Stated, not
  changed in code: the README's hook section has the exception, and so have the two source
  comments that claimed "writes nothing" for this check (the hook script's header, the
  docstring of `unstaged_map_pages`). The code-map skill makes that claim only for `changed`
  and for the session-start hook, where it holds, so its text stays as it was (19,999 of
  20,000 characters). Left out: skipping the filtered hash for LFS-tracked pages, which would
  drop the staged-map check for exactly those pages.
- **Not verified.** As in entry 13: no compaction of a real manager run has been observed, and
  no run of this version is recorded.

### 15. Trainer skills removed (plugin 0.9.3)

The owner's call: the optional per-skill trainer skill (`<name>-trainer`) did not work in
practice, so self-training-skills no longer offers or writes one.

- **Removed.** Create mode's trainer step and its Turkish question template (the later step is
  renumbered; Train's step numbers are unchanged), the trainer in the skill's **What it is**,
  **Formats**, **Adopt** and **Report** texts and in the script's usage, the file
  `references/trainer-template.md`, the README's "optional trainer skill", and "their trainers"
  in the manager's `references/self-training-due.md`. `skilltrain.py` loses its trainer checks
  (the five trainer sections, the `## Trains` pairing with a worker) and `due` no longer adds
  `[trainer: ...]` to a worker's line. The skill's text went from 12,008 to 10,434 characters.
- **Moved into the worker template.** The trainer's three rules that held up now sit in the
  `## Record` section of `references/skill-template.md`, as three bullets: an owner reaction in
  conversation ("kaydet", "iyi oldu", "kötü oldu", "hangisi daha iyi") gets one row (`owner
  session`, `owner-good` / `owner-bad` else `n/a`, the owner's words verbatim, domain
  measurements as `key=value` in the note); compared with the previous attempt, more than one
  change gets the tag `confounded`; the next experiment changes one variable at a time, with the
  same seed and inputs. `records-format.md`, `evidence-rules.md` and the script already accepted
  these outcomes and the tag; they are unchanged.
- **Existing trainers are retired, not validated.** The script still knows the old marker
  `<!-- self-training-trainer v1 -->`, only to report it: `check` and `stats` on such a folder
  print one line, `<path>: retired trainer (self-training-skills 0.9.3 dropped trainers): delete
  this folder; its worker's Record section now holds its rules`, and exit 1; `due` prints the
  same as that folder's line and exits 0 as before. Tests: the three trainer-validation tests
  went, one test covers the retired behaviour of `check`, `stats` and `due`, and the template
  test no longer writes a trainer.
- **Not verified.** [not measured] No live session has used the new `## Record` bullets, and no
  project's existing trainer has been retired with this version.

### 16. Working notes in a file, a context line once per crossing (plugin 0.9.4)

Seen in a live manager run: the orchestrator printed its whole "Manager working notes" block
(about 3,700 characters) as a visible message again and again, each time followed by "context
grew, run /compact". Two causes: the context hook spoke after every subagent return while the
context stayed above the budget (200,000 tokens; with parallel implementers and auto-compact at
300k that is every return in between) and told the orchestrator to write its working-notes lines
out; and the skill never said where those lines live, so they lived as visible text and were
printed whole. Each print cost some 1k tokens or more and brought the next compaction closer.

- **The notes live in a file.** The manager skill's **Run marker** paragraph: the working-notes
  lines are kept in `~/.claude/manager-runs/notes/<session id>.md`, written when the marker is
  (`mkdir -p`; a new run starts it fresh, a compaction of the same run keeps it; outside every
  repository), changed a line at a time (the Edit tool), never printed as a block (**Talking to
  the owner** says the same); a file that can't be written → each line stated once in the
  conversation, when it is set or changes. Both files are removed (`rm -f`) when the run ends; the
  hooks' "if no manager run is in progress any more" lines name both files, so a file left behind
  is named for removal too. The notes folder is its own, beside `active/`, so the marker glob of
  the context hook and the compaction hook's marker test are unchanged; a test holds that a notes
  file is no marker for either. Step 0's re-read after a compaction names the notes file as the
  hook prints it; `references/model-strategy.md` reads the strategy line from the notes file (or,
  without one, the summary). The other references that keep a working-notes line stay as they
  were: their wording holds for a file too.
- **The compaction hook.** `SessionStart` (`compact`) prints, after its re-read line, the notes file
  verbatim, whole lines while they fit in 8,000 (as the shell counts `${#var}`: bytes in dash,
  characters in bash; at most 8,000 characters either way), and a last line when it cut, so the
  whole output stays under Claude Code's 10,000 characters (tested with ASCII, two-byte and
  three-byte lines). `PreCompact` with a notes file: a short instruction, the notes are in that
  file and come back after the compaction, keep only a line not yet in it; without one, the old
  verbatim-lines instruction stands. Still plain sh with `cat`, `grep`, `sed` and the shell's own
  `read`; it writes nothing, fails open, and is silent without the marker, in a subagent and for a
  bad id.
- **The context hook speaks once per crossing.** Its line now says: make sure the notes file is
  current (never print the notes), and suggest `/compact` to the owner once, at the next stop. It
  speaks when the last request is above the budget and the previous request that called the Agent
  or Task tool was at or under it, both read from the transcript's end as before (`usage.back`,
  which `usage.last` now uses too). That earlier request is the hook's previous chance to speak:
  the hook runs when an Agent call ends (a subagent's return; a background one,
  `run_in_background`, is assumed to end at its launch, which is not verified), and the
  orchestrator's requests between two such calls (git, `gh`, reads) run no hook, so comparing with
  the request just before the last would miss most crossings. Stateless: nothing is stored. The
  scan stops at the transcript's last `compact_boundary` record: no earlier Agent call since then,
  or in the end it reads (1 MiB) at all → it speaks, as before. So after a compaction the next
  crossing speaks again, whatever came before the boundary. Several subagents spawned in one
  message (their hooks all follow that one request): the line comes only at the hook whose input's
  `tool_use_id` is the message's first Agent or Task call, read from that request's records in
  order; no id in the input, or one not among them → it comes, as before. `MANAGER_CONTEXT_BUDGET`
  stays.
- **Ceilings.** The manager skill went from 17,995 to 17,986 of its 18,000 characters: the new text
  was paid for by shorter wording elsewhere (the GitHub backend and lean-context bullets, a
  cross-reference in loop step 2, the parenthetical list in **Owner decisions** item 1 that
  `owner-decisions.md` holds anyway, the no-report line, step 0 item 5). The code-map skill and
  the brief ceilings are unchanged.
- **Not verified.** [not measured] No live session has run this version: whether the orchestrator
  keeps the file current and stops printing the block, whether a summary drops lines when told
  they come back from a file, and how often the context line now comes in a real run. [not
  measured] When a background Agent call runs its `PostToolUse` hook (assumed: at launch). [not
  measured] Whether Claude Code writes a message's parallel tool calls as one record or one per
  call: both shapes are tested. No eval was run (`claude plugin eval` not approved for this
  change).
- **Known limits, not fixed.** An Agent call that runs no `PostToolUse` hook (denied, or failed
  before the hook) still counts as the previous chance in the transcript, so the next crossing
  check can stay silent; the same holds when a batch's first call is the one without a hook. The
  compaction hook's 8,000 cap counts bytes (dash) or code points (bash), not the UTF-16 units a
  JavaScript string length counts: a notes file full of characters outside the Basic Multilingual
  Plane could, under bash, come to more than 8,000 such units (still under 10,000 in total only
  while those are few).

### 17. Skill map: check routing, lessons and triggers, query, a skills-first search block (plugin 0.9.5)

A description trigger was dropped in two separate migration phases, and both times only review
caught it; a skill's routing to its reference files was checked only by hand.

- **`skilltrain.py check`** (marked worker skills only) now also checks the routing. A
  `## Knowledge` routing is a bullet that starts with one path in backticks (the template's form,
  now `` `<path>` — read when <...>``); a path that starts with `references/` is in the skill's
  folder, any other is from the repository root. Every routed path must exist (a file or a
  folder; `knowledge routing points at a missing file: <path>`), and every file under the
  skill's `references/` needs a routing of its own (`references/<file> has no routing in ##
  Knowledge ...`; a folder's routing doesn't cover its files; dot files and symlinks are left
  out). Backticked text that holds whitespace, `://`, `*` or `?`, or starts with `<` (a command,
  a URL, a glob, a placeholder) is no routing and is not checked as a path (review fix round 1).
  A cited lesson id missing from `lessons.md` was already a problem; it has its own test
  now. Exit codes unchanged: 0, 1 with one line per problem, 2 for a bad path.
- **`check --triggers-from <ref>`.** Every quoted phrase (straight `"..."` or curly `“...”`; a
  YAML double-quoted description's `\"` and a single-quoted one's `''` are unescaped first) in the
  skill's description at the ref, and in the description of the folder `<name>-trainer` beside
  it at the ref (the retired trainer), must still be in the current description (whitespace
  collapsed, case kept). A dropped one is a problem that names the phrase and its source (`from
  the skill's description` / `from the trainer's description`, with the ref and the path). Choices:
  a ref that isn't a commit, a folder that isn't in a git repository, or no git → exit 2 with a
  `--triggers-from: ...` line (an error: in Adopt the check is mandatory, so it must never pass
  silently); a skill missing at the ref is new → a `note:` line, not a problem; a trainer missing
  at the ref is skipped silently (most skills never had one). git is run read-only (`rev-parse`,
  `ls-tree`, `cat-file`); a symlink at the ref counts as missing. Adopt mode runs `check <skill
  dir> --triggers-from <base ref>` after marking a skill.
- **`skilltrain.py query <repo root> <term>`.** One line per matching line of every marked
  skill's `SKILL.md`, `references/` files, `lessons.md` (with the row's lesson id) and records file
  (from its `Records:` path): `<skill>: <file>:<line>[ L<n>]: <text>`, case-insensitive, at most
  50 lines, then `(cut: <n> more hits; use a longer term)`, as code-map's `query` caps its lists.
  Exit 0 with hits, 1 with none (also with no marked skill), 2 for a bad path or an empty term. A
  term that starts with `-` goes after `--` (`query <root> -- -rf`); the hook's printed command
  always puts `--` before the term. It reads the files on
  every call and writes nothing.
- **No duplicate work.** Create and Adopt first look for a project tool that already maps or
  checks its skills and use it; replacing it is an owner decision. The implementer brief says
  "duplicate no existing project script or test" (paid for with shorter wording in the same
  step and in step 1; 1,327 → 1,326 words), and `brief-skill-records.md` gives the skill-phase
  detail (use it, or `NEEDS_OWNER_DECISION` to replace it; run `check`, with `--triggers-from` when
  the phase marks or migrates a skill, and `rules-hint`).
- **One instruction line.** "before searching skill files use `skilltrain.py query`; after
  changing a skill run `skilltrain.py check`" is in the skill's SKILL.md, and `skilltrain.py
  rules-hint <repo root>` (`--remove`) puts it in the project's rules once: a line ending with
  `<!-- manager-plugin:self-training-skills -->`, updated in place where it already is
  (`AGENTS.md` or `CLAUDE.md`; a second copy is dropped), else appended to `CLAUDE.md` (created
  with a title if missing, its marker then saying so), and only when the repository has a marked
  skill. `--remove` deletes a `CLAUDE.md` it created when only its title is left, and leaves
  every other file. Not added to
  code-map's block: that block is versioned against a template the code-map SKILL.md prints for
  the no-Python case (at 19,999 of 20,000 characters), a conditional block would break the
  version check, and a project with marked skills may have no code map at all.
- **The manager runs it.** `self-training-due.md` runs `check` on each marked skill and lists the
  problems before the decision batch; `final-report.md` names that line. When a phase of the run
  changed the skill it adds `--triggers-from <merged SHA>^1`, the merged SHA of the run's first
  landed phase (the final report lists merged SHAs, and the plan's status lines and GitHub give
  it back after a compaction or in a new session); no phase landed → no `--triggers-from`. The
  `HEAD` equals `origin/<default>` gate covers `check` as well as the grep and `due`.
- **Skills first, a branch of the search hook.** Same hook, same fast path. A Grep, Glob or Bash
  search whose path or file pattern (Grep's `glob`, find's `-name`/`-path`, rg's `-g`, grep's
  `--include`) targets `.claude/skills/`, `SKILL.md`, `lessons.md`, a skill's `references/` or
  a marked skill's records file, in a repository with a marked skill, is blocked once per
  session (exit 2, one `manager-plugin: skills first:` line naming `<python>
  "<plugin>/skills/self-training-skills/scripts/skilltrain.py" query "<repo root>" -- "<term>"`, the
  term taken from the search pattern, else `<term>`); repeated, it is allowed. (The brief first
  asked for a non-blocking `additionalContext` note; the owner changed it to block like the
  code-map branch.) Its state is its own marker file, so it neither uses up nor gets the code-map
  block, and a skill search gets only this branch. It needs no map: no `.codemap.json` → on; one,
  map or not, with `"search_nudge": false` → off. What counts (review fix round 1): a wildcard
  path or file pattern with a `skills` part (`find -path "*/skills/*"`); one with a `references`
  part (Glob `**/references/*.md`) only when a marked skill has a `references/` folder; records
  only at a marked skill's `Records:` path, its folder, or that folder's parent when it is named
  `skills` (so `src/skills/a/records.md` no longer counts). With no marked skill the branch
  steps aside and the search goes to the code-map branch exactly as before 0.9.5 (a broad `find
  . -name SKILL.md` gets the map-first block, a narrow `.claude/skills` search is allowed); this
  is tested. (Before the fix round it was silent there instead, so the code-map block was lost
  for such a search.)
- **Ceilings.** Manager SKILL.md 17,986 and code-map SKILL.md 19,999: unchanged (no edit). The
  self-training-skills SKILL.md went from 10,434 to 13,720 characters (no ceiling).
- **Not verified.** [not measured] No live session has hit the skills-first block, so whether
  sessions run the suggested `query` and whether the derived term helps is unknown. [not
  measured] No real project's skills have been run through the new routing or trigger checks; an
  existing skill whose `## Knowledge` bullets start with a backticked command or a placeholder
  will now fail `check` (a command, URL, glob or placeholder no longer does). No eval was run.
- **Known limits, not fixed.** Trigger matching is a substring test and case-sensitive: a phrase
  kept only inside a longer word, or with other casing, counts as kept or dropped accordingly.
  The hook's term comes from the last search pattern it sees, so `grep -e a -e b` suggests `b`.
  A non-wildcard path named `references` outside `.claude/skills/` never counts as a skill
  search. Rebase merges: when the run's first landed phase was rebase-merged with more than one
  commit, `<merged SHA>^1` is not the default branch from before the run, so a trigger dropped in
  an earlier commit of that phase goes unreported; the value is exact for squash and merge-commit
  landings. A reference file whose path contains a space can't be routed (backticked text with
  whitespace is no routing), so it always fails with "has no routing". `rules-hint --remove` can
  leave an extra blank line in a `CLAUDE.md` it created.

### 18. Whole-disk scans refused, script paths handed to every agent (plugin 0.9.6)

On Windows 11 / Git Bash, subagents twice ran `find / -name codemap.py -path *manager*`; the
processes outlived their agents for hours, held millions of handles, and the paged pool reached
8.9 GB with under 1 GB of RAM free. A written rule did not stop it. The cause: an agent told to
use the code map had no path for `codemap.py` (the plugin's agents only ran a command a hook
named; the rules block names the skill, not a path).

- **Scan guard**, a new `PreToolUse` hook on `Bash|PowerShell|Glob|Grep` (`hooks/scan-guard.sh`,
  logic in `skills/code-map/scripts/scan_guard.py`, beside `search_nudge.py`, whose tokenizer,
  find/grep/rg parsing, `plugin_command` and state it reuses). It refuses (exit 2, one line on
  stderr) a recursive scan of a filesystem root, a drive root or the home folder: `find`, `ls -R`,
  `du`, `tree`, `grep -r`, `rg`, `ag`, `ack`, `fd`; PowerShell `Get-ChildItem`/`gci`/`dir`/`ls`
  with `-Recurse` (any case, any abbreviation, `-Depth` above 1, `-Path`/`-LiteralPath`, named or
  positional; `-Depth 0|1` is a listing, as find's `-maxdepth 0|1`), `cmd /c dir /s`, `cmd /c
  tree`, `where /r`. Roots: `/`, `/c`, `/cygdrive/c`, `/mnt/c` (any letter, any case; in a POSIX
  shell only: in PowerShell and cmd, `/c` is a folder or a switch), `C:`, `C:/`, `C:\`, `\`, `~`,
  `$HOME`, `${HOME}`, `$env:USERPROFILE`, `$env:HOMEDRIVE\`, `%USERPROFILE%`, `/home`, `/Users`,
  `C:\Users` (also as `/c/Users`), `/root`, the literal `HOME`/`USERPROFILE` path (unless it is
  itself a repository's top, e.g. a container with `HOME=/app` holding the repository), and
  `<root>/*`. In PowerShell and cmd, `find` is find.exe and `tree` tree.com: their `/x` switches
  are dropped before the path check (`tree /f`, `tasklist | find /i "python"`, `find /c "x"
  file.txt` pass). Commands are tokenized (the nudge's shell tokenizer, a PowerShell one, a cmd
  one) and `bash -c`, `sh -c`, `powershell -Command`, `pwsh -c` and `cmd /c` strings are scanned
  again, as are pipes, chains, subshells, `$( )` and backticks (also inside double quotes);
  here-document bodies are text. Relative paths count from the cwd, which follows
  `cd`/`Set-Location`, so `find .` in a root cwd, `cd / && find .` and `find ../..` up to `/home`
  are refused. Glob and Grep: a root `path`, or none in a root cwd; Glob also a pattern that
  recurses (`**`) from a root (`/**/x`, `C:/**/x`, `~/**/x`). An unparseable command (an unbalanced
  quote) only gets the `find <root>` token check. It has no off switch and `"search_nudge": false`
  doesn't touch it (an off switch, proposed, not built: an environment variable such as
  `MANAGER_PLUGIN_SCAN_GUARD=0` in the settings' `env` block).
- **The message** names why (hours, memory), the absolute code-map `query` command (with `--root
  "<repo>"`), the absolute `skilltrain.py query "<repo>" -- <term>`, a search limited to the
  repository (`rg <term> "<repo>"`, `find "<repo>" -name <x>`, `timeout 120` in front of a long
  one), and that the scripts never need to be searched for (when the plugin folder can't be
  resolved, the skills are named instead and the paths are said to come at session and agent
  start). Without Python, the sh script itself refuses only a `find [-H|-L|-P]... [--] <root>` at
  the start of a command (or after `;`, `&`, `|`, `(`, a backtick or a newline), in a Bash call's
  `command` value taken from the raw input (PowerShell calls and other fields such as `description`
  are never matched), with a message naming the repository-limited search only; otherwise it fails
  open. Python starts only when the input names Glob, Grep or a scan word.
- **The map-first nudge** imports the guard's predicate (`scan_guard.refused`) and leaves a refused
  command alone, so it doesn't use up the nudge's once-per-session block (the hooks of one event
  run in parallel). `search_nudge.find_paths` now skips a `--` (`find -H -- /`).
- **Timeout hint.** For an allowed recursive scan in Bash (`find`, `grep -r`, `rg`, `ls -R`, `du`,
  `tree`) not under `timeout`, a `PreToolUse` `additionalContext` with no permission decision, once
  per session (each subagent its own; the nudge's marker folder, its own key): "long recursive
  scans: prefix `timeout 120`". Nothing is wrapped or rewritten; none for PowerShell. [not
  verified] that `timeout` exists in every Git Bash.
- **Script paths at start.** `hooks/agent-paths.sh` (logic: `scan_guard.py start`) on
  `SubagentStart` (every agent type) and `SessionStart` (`startup|resume|clear|compact`): in a
  repository (`.git`, else `.codemap.json`, walking up) with a `.codemap.json`, a `<!--
  manager-plugin:code-map` or `<!-- manager-plugin:self-training-skills` marker in
  `AGENTS.md`/`CLAUDE.md`, or a marked self-training skill, one `additionalContext` line with the
  absolute `codemap.py query` and `skilltrain.py query` commands and "never search the disk for
  these"; elsewhere nothing. A new script rather than the rules-version one: that one is bound to
  `startup|resume|clear`, `compact` belongs to the manager-run script, and SubagentStart needs JSON
  output. The line carries paths only, no instruction about the work, so the reviewer's
  independence is untouched.
- **Agents and briefs.** `worker.md`, `researcher.md`, `fallback.md`: the absolute commands come in
  the start context and in hook messages; never search the disk for plugin scripts.
  `brief-skill-records.md`: `skilltrain.py` is the `Code map` command with
  `code-map/scripts/codemap.py` replaced by `self-training-skills/scripts/skilltrain.py` (`Code
  map: none`: the start context's). The implementer and reviewer briefs are unchanged (1,326 and
  1,347 words). The commit check and the nudge already printed absolute commands (checked). The
  `AGENTS.md`/`CLAUDE.md` rules block is unchanged and names no path (a plugin path is machine- and
  version-specific and would leak a user path into the repository): no template version bump.
- **Ceilings.** Manager SKILL.md 17,986 and code-map SKILL.md 19,999: unchanged (no edit).
- **Not verified.** [not measured] Live behaviour on Windows, Git Bash and the PowerShell tool: the
  guard and its tests ran on Linux with synthetic hook input only, so whether a live PowerShell
  call arrives as tested, and whether `SubagentStart`'s line reaches a subagent as the
  documentation says, is unobserved. No eval was run.
- **Known limits, not fixed.** Paths built at run time (`find $ROOT`, `find "$(pwd)"`), a `cd` to a
  variable (the cwd is then unknown), `eval`, script files (`bash scan.sh`), `-EncodedCommand`,
  `Invoke-Expression`, `Start-Process` and scans in other languages (`python -c "os.walk('/')"`)
  pass. Other top-level folders (`/usr`, `/opt`, `C:\Program Files`, `/Volumes`) and other users'
  homes (`~bob`) are not roots. `locate` reads a database, not the disk, and passes. A home folder
  that is a repository's top passes under its literal path, but `~` and `$HOME` stay roots, so a
  dotfiles repository in `~` scanned as `find ~` is refused; a repository at `/`, `/home` or a
  drive root gets its whole-repository scans refused. Glob with a root `path` is refused even for a
  one-level pattern; `du -d 0 /` is refused (it still walks the tree). PowerShell's `-r` is taken
  as `-Recurse`. In PowerShell and cmd, `rg foo /c` is not refused (`/c` is no root there), and a
  find.exe-style `/x` argument to `find` or `tree` is taken for a switch. The no-Python fallback is
  a text match on the command value: it misses `find . /`, `sudo find /` and every wrapper (a `find
  /` after a `;` inside a quoted `bash -c` string is caught, one at its start is not), and it also
  matches inside a quoted string such as `echo "a; find / x"`. Here-document detection is
  approximate.
- **Orphaned processes.** A scan that outlives its parent agent is a Claude Code process issue (the
  child is not ended with its agent); the plugin can only keep such scans from starting.

### 19. Hook wrappers and tests portable to Windows (plugin 0.9.7)

Run on a Windows 11 machine (Git Bash, Python 3.13 as `py -3`; `python3` and `python` there are
Microsoft Store stubs that exit 9009), the 0.9.6 unit tests failed in about 40 hook tests and in
a set of others. The live guard itself was checked there and works [measured]: a Bash `find /`
and a PowerShell `Get-ChildItem C:\ -Recurse` both exit 2 with scan_guard.py's message when the
hook gets valid JSON. No guard logic changed.

- **Wrappers.** The tests start a hook as `sh <os.path.join(...)>`, so `$0` is
  `C:\...\hooks\scan-guard.sh`: `${0%/*}` stripped nothing, the script path beside it didn't
  exist, and the wrappers fell to the no-Python fallback (scan-guard.sh) or printed nothing
  (agent-paths.sh; the tests then got `None`). Every hook that finds its script from `$0`
  (agent-paths, codemap-commit-check, codemap-rules-version, codemap-search-nudge,
  manager-context-watch, scan-guard) now takes its folder as `here=${0%[/\\]*}` (up to the last
  `/` or `\`), and the three that pass the plugin root (agent-paths, codemap-search-nudge,
  scan-guard) take `$0` as absolute for `/*`, `[A-Za-z]:[/\\]*` and `\\*`, not only `/*` (a
  drive-relative `C:x\...` is not). A `/` path
  gives what it gave before (a test compares the two). prefer-plugin-agents.sh,
  manager-run-compact.sh and retro.sh don't use `$0`: unchanged. `hooks/test_wrapper_paths.py`
  runs each wrapper's own lines in sh with `C:\`, `c:/`, mixed, UNC and relative `$0` values
  (from a script file with `$0` read as `$1`: through `sh -c` on Windows the command line's
  parsing changed the backslashes of `[/\\]`), and
  runs scan-guard, the search nudge and agent-paths for real through a `$0` whose separators are
  backslashes (a file named `plugin\hooks\<name>.sh` beside a folder of that name, on Linux); with
  the 0.9.6 wrappers those three fail.
- **Line endings.** The repository had no `.gitattributes` and that machine has
  `core.autocrlf=true`, so every `.sh` was checked out CRLF (sh still ran them). Now `*.sh`,
  `*.py`, `*.md`, `*.json` and `*.yaml` are `text eol=lf` (`.md`: `test_plan.py` reads
  `docs/LIVING_PLAN.md` byte for byte; the skills' size ceilings count characters). Every file was
  LF in the index already: renormalizing changed nothing.
- **Tests.** A shared, stdlib-only `plugins/manager-plugin/portability.py` (imported by the tests
  only; on POSIX each helper is the plain call):
  - the Python a hook names in its message is the first of `python3`, `python`, `py -3` that runs
    under sh, as the wrappers pick it (`hook_python()`), not a literal `python3`; the tests that
    run `codemap.py` themselves use `sys.executable`. This also explains the `git update-index`
    `CalledProcessError`: the commit-check test built its map with `python3`, the Store stub, so
    the map page was never in the index for `update-index` to mark;
  - every text `open()` in the tests reads and writes UTF-8 (the code-map `read` helper decoded
    with cp1252 there);
  - `symlink()` skips the test on Windows when creating a symlink needs a privilege (WinError
    1314); elsewhere an error still fails it;
  - `rmtree()` is the plain call off Windows; on Windows it clears read-only (git's read-only
    objects, WinError 5; never through a symlink) and retries, retries a held file a few times
    and then leaves it (WinError 32); `temp_dir()` is a `TemporaryDirectory` that ignores cleanup
    errors on Windows;
  - `slashed()`: on Windows the hooks print paths with `/` (search_nudge.quote_path and codemap's
    rules hint, on purpose: Git Bash and PowerShell both take them), so the expected messages use
    that form there; and a test that puts a path into a Bash command uses it too (Bash reads an
    unquoted `C:\Users\x` as `C:Usersx`, so those commands named no such path);
  - skipped on Windows, each with its reason: the two `"a".py` tests and the `notes/m*.md` map
    page test (no such file names there), the long-path batching test when its paths pass
    MAX_PATH from the temporary folder, the 0o777 shared-state-folder case of the nudge (no mode
    bits), the `0o750` mode check after `uninstall-hook` (the reported `438 != 488`: 0o666 against
    0o750, a mode, not a byte count), and the retro switch's no-`HOME` case (Git Bash's sh sets
    `HOME` when it is unset);
  - evals: the scaffold scripts run with Git Bash (`bash.exe` beside `sh`, else under the Git
    install, else a `bash` on PATH outside System32), never System32's `bash.exe`, which starts
    WSL; without one the scaffold tests skip with that reason.
- **Version.** plugin.json 0.9.7 (marketplace.json carries none). README: the hooks find their
  scripts from a `C:\...` path; how to run the tests on Windows.
- **Ceilings.** Manager SKILL.md 17,986, code-map SKILL.md 19,999, implementer brief 1,327 words,
  reviewer brief 1,347: unchanged (no edit).
- **Measured on Windows** (the first version of this change): code-map, self-training-skills,
  manager, living-plan and evals passed; hooks failed 28 of 153. The hooks then resolved their
  scripts and named `py -3` (so the wrapper fix and `hook_python()` held there); the failures were
  the `/` message paths, `sh -c` mangling the snippet test's backslashes, a hard-coded
  `src/tmpin`, and Bash commands built from `\` paths. Those are fixed above.
- **Not verified on Windows.** [not verified on Windows] that the hooks suite now passes there,
  after those fixes (run on Linux only), and that MSYS sets `HOME` when it is unset.

### 20. Restart after an update, test hardening (follow-up to 0.9.7; no version bump)

A new entry rather than more lines in 19: 19 records what 0.9.7 shipped, and this changes no
shipped behaviour, so plugin.json stays 0.9.7.

- **Incident.** A long-running session that had started before the plugin update kept the 0.9.5
  hooks (no scan guard). Its reviewer subagent ran `find / -maxdepth 6 -name codemap.py`; the
  process outlived the agent and held about 360k handles until it was killed. Hooks and agent
  definitions load at session start, and an update doesn't reach a session already open
  (`claude plugin update --help`: "restart required to apply").
- **README** (Install): updating takes `claude plugin marketplace update vanvia-manager` (the
  listing only) and then `claude plugin update manager-plugin@vanvia-manager` (`--scope
  project|local` for those installs; on a Windows machine it reported 0.9.6 to 0.9.7 for scope
  user and asked for a restart). After an update, restart open sessions (`/exit`, then `claude --resume`
  keeps the conversation); `/reload-plugins` is named as the docs' alternative, not tried with
  these hooks. A stale project- or local-scope install is updated at its own scope; uninstall
  it only to drop that scope (a project-scope uninstall edits the committed
  `.claude/settings.json`, which turns the plugin off for teammates and cloud sessions). The docs
  give local over project over user for a plugin's setting; [not verified] that an old copy at a
  higher scope keeps loading after the user-scope one is updated.
- **.gitattributes:** `.gitignore` and `.gitattributes` are `text eol=lf` too (a Windows
  checkout had `evals/.gitignore` CRLF). Renormalizing changed nothing.
- **portability.rmtree** (Windows handler only): a retry calls the failing function again only
  when it is `os.unlink`, `os.remove` or `os.rmdir`; a failed `os.scandir` (or `lstat`, `open`)
  is never called again, which leaked a directory handle each time. Off Windows: plain
  `shutil.rmtree`, unchanged.
- **Test.** `hooks/test_wrapper_paths.py` `RealPathTest`, skipped nowhere: scan-guard.sh,
  codemap-search-nudge.sh and agent-paths.sh run as `sh os.path.join(HERE, name)` with
  `CLAUDE_PLUGIN_ROOT` unset; each must give its Python script's output (not the fallback, not
  empty) naming `portability.slashed()` of the plugin's own `codemap.py` (and `skilltrain.py`
  for agent-paths). A wrapper that splits `$0` at the platform's wrong separator fails it
  (checked on Linux with `here=${0%\\*}`: 3 of 3 fail). [not verified on Windows] that it
  passes there and fails with `here=${0%/*}`.

### 21. Scan guard adversarial corpus (plugin 0.9.8)

The scan guard's tests were hand-picked tables. A data-only corpus now measures both failure
kinds: a leak (a root scan that passes) and a false block (normal work refused).

- **Corpus.** `hooks/scan_guard_corpus.json`: 336 entries (182 block, 154 pass; Bash 245,
  PowerShell 58, Glob 20, Grep 13), one entry per line: `cat`, `tool`, `input` (the tool input),
  optional `cwd` (default per tool in the file's header, as is the `HOME` it assumes), optional
  `env` (variables set for the entry), optional `dirs` (paths, expanded and with `/`, that the test
  makes `os.path.isdir` report as folders), `expect` (`block`|`pass`), `note`, optional `known_gap`
  (why the predicate gets it wrong) or `hook_gap` (why only the sh hook does). JSON rather than
  TSV: stdlib, typed, and commands carry tabs, newlines (here-documents) and quotes that a TSV
  would have to escape. Categories: incident (including the
  `cd <repo> && sed ...; find / -maxdepth 6 -name codemap.py ...` command that ran for hours on
  Windows), root-spelling, scanner, wrapper, composition, quoting, cwd-root, glob-grep, powershell,
  bait (repository, scratchpad and plugin folder scans; listings; text, commit messages and PR
  bodies in Claude Code's `"$(cat <<'EOF' ... EOF)"` form, here-document bodies with `<<\EOF`,
  `<< \EOF` and `<<'END TEXT'` delimiters, a here-document to a shell inside a quoted argument or
  an ANSI-C `$'...'` string, dotted folders under a root in every spelling, URLs), gap.
- **Test.** `hooks/test_scan_guard_corpus.py` runs every entry through `scan_guard.refused` (the
  predicate) and through the real `sh hooks/scan-guard.sh` (the hook: its grep pre-filter and its
  Python lookup), and prints, per category and for each level, the entries, leaks, false blocks and
  known gaps (stderr). The hook runs for every entry that is to be refused or that the predicate
  refuses (about 180 runs, 5 s on Linux); for the rest it exits 0 whatever the pre-filter does, so
  its result is the predicate's. Entries with `dirs` take the predicate's result (a mock can't
  reach a subprocess). Any mismatch not marked fails, as does a hook result that differs from the
  predicate's without a `hook_gap`, and a marked entry that no longer mismatches (so its mark is
  dropped). On Windows the hook gets the Windows-form home `C:\Users\tester` and the hook input
  spells the corpus home that way: Git Bash converts a POSIX `HOME=/home/tester` into
  `C:\Program Files\Git\home\tester` for the Windows Python it starts, which no entry names (found
  on the Windows 11 check at cb0b76d; checked on Linux by forcing that home, [not verified on
  Windows] until rerun). Also: a dotted folder in a real temporary home (`dir /s .\my.app` passes,
  `.\codemap.py` and `.\*.py` are refused, predicate and hook); timing (under 1 s each) for 63 KB
  of `cat <<A <<A ...`, for `echo '` + 9,000 `sh <<B` + `'` (here-document dropping, one pass per
  line), and for a command over the length cap.
- **Decisions.** `find -maxdepth 0|1` at a root passes (a listing, as before; GNU find applies
  `-maxdepth` wherever it stands, so `find / -name x -maxdepth 1` passes too), consistent with
  PowerShell `-Depth 0|1`; now also `rg -d|--max-depth 0|1`, `fd -d|--max-depth|--exact-depth 0|1`
  and `ag --depth 0|1`. `du` stays refused at any depth (`du -d 0 /` still walks the tree).
  `-EncodedCommand` (any of `-e`, `-ec`, `-enc`...): decoded (base64 of UTF-16LE) and scanned as
  PowerShell; undecodable: passes (fail open). A Bash or PowerShell command over 64 KB is not
  scanned at all (passes): shlex and the tokenizers are superlinear on one long word (a 160 KB
  base64 argument about 1 s, 850 KB 24 s, measured on the 0.9.8 review), the hook would outlive its
  time budget, and no hand-written scan is that long. The whole scan is skipped, not only the
  decode, because the time goes into tokenizing the word, before any decode.
- **Here-documents: bodies are text, always.** A here-document's body is never scanned as commands,
  whatever it is fed to: `bash <<'EOF' ... find / ... EOF` and `sh -s <<X ... X` pass (known gaps).
  Scanning the body of a here-document fed straight to a shell was built in this change and removed
  again (owner's decision) after three review rounds each found new false blocks from it: a `<<`
  line inside a quoted commit message, PR body or Python string; the same inside Claude Code's
  `"$(cat <<'EOF' ... EOF)"` form with an odd quote in the text; and backslash-quoted or spaced
  delimiters (`<<\EOF`, `<<'END TEXT'`) the opener pattern didn't read. Body lines are dropped
  before the command is parsed. The opener pattern now reads `<<WORD`, `<<-WORD`, `<<\WORD`,
  `<< \WORD`, `<<'WORD'` and `<<"WORD"` (quoted: spaces allowed); that fixes a false block since
  0.9.6 (`cat > notes.md <<\EOF` with `find / -name x` in the body). A `<<` (not `<<<`) whose
  delimiter can't be read (`$((1<<2))`, `<< ""`) stays text, as in f3a720f, and the rest of the
  command is scanned. A `<<WORD` inside quotes is still taken for an opener and drops the lines
  after it up to `WORD` (as in f3a720f). When that leaves text shlex can't split but the command as
  written splits (an opener inside a quoted commit message), the command passes: no refusal, and
  the token fallback is not run on it (fail open). When the command as written doesn't split either
  (`cat <<EOF ... EOF` then `echo $'it\'s'; find / -name x`), the token fallback runs on the text
  without the bodies, as in f3a720f.
- **Dotted leaves for `dir /s`.** `dir /s <root>\x.y` counts as a search for the file `x.y` over
  the whole root only when `x.y` is not an existing folder. The spelling is expanded first (`~`,
  `%VAR%`, `$env:NAME`, `${NAME}`, `$NAME`; PowerShell's `$HOME` falls back to `USERPROFILE`), and
  one that can't be expanded (an unset variable, `~user`) keeps the leaf: taken for a folder, it
  passes, so `dir /s %USERPROFILE%\codemap.py` with `USERPROFILE` unset where the hook runs is a
  miss. Quotes are dropped from the path first. Limitation: where the hook can't see the folder (a
  Windows path checked on Linux, a variable set only in the target shell), a dotted folder that
  exists on the user's machine is refused as a file search; the corpus makes such folders exist
  with `dirs` and `env`. A wildcard leaf (`C:\*.py`, `gci C:\*.py -Recurse`) is always its folder.
- **Before and after**, leaks / false blocks, the gaps not counted; predicate | sh hook (they
  differ only in the hook gap, counted as a gap). Before is f3a720f (0.9.7), after is this change;
  the round-by-round numbers at 8b20f4b, 5b0d737 and 8275cc7 are in PR #61:

  | category | entries | f3a720f | after |
  | --- | ---: | ---: | ---: |
  | bait | 61 | 0/2 \| 0/2 | 0/0 \| 0/0 |
  | composition | 26 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | cwd-root | 30 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | gap | 4 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | glob-grep | 33 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | incident | 3 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | powershell | 49 | 10/1 \| 10/1 | 0/0 \| 0/0 |
  | quoting | 20 | 0/0 \| 0/0 | 0/0 \| 0/0 |
  | root-spelling | 33 | 4/0 \| 4/0 | 0/0 \| 0/0 |
  | scanner | 45 | 5/3 \| 5/3 | 0/0 \| 0/0 |
  | wrapper | 32 | 11/0 \| 11/0 | 0/0 \| 0/0 |
  | total | 336 | 30/6 \| 30/6 | 0/0 \| 0/0 |

  Gaps: 15 for the predicate, 16 for the hook (the hook gap below), the same entries at f3a720f.
  f3a720f's bait false blocks are `cat > notes.md <<\EOF ... find / -name x ... EOF` and a
  double-quoted commit message with `cat <<EOF` and a newline in it. No gap is new with this
  change.
- **Fixes** (scan_guard.py, local, same design): `eval` arguments scanned as Bash; the
  here-document opener pattern, as above; wrappers `time -p`, `command -p` (`command -v|-V` is a
  lookup), `exec -a`, `ionice`, `busybox`; `powershell.exe`'s bare script after its options
  (`powershell gci C:\ -Recurse`, value options such as `-ExecutionPolicy Bypass` skipped; pwsh
  takes a bare word as a file); `-EncodedCommand`; `iex` and `Invoke-Expression` strings scanned as
  PowerShell; a root spelling followed only by `..` is a root (`~/..`, `$HOME\..`); a Windows-form
  home (`HOME` or `USERPROFILE` `C:\Users\x`) in its Git Bash, Cygwin and WSL spellings
  (`/c/Users/x`, `/cygdrive/c/Users/x`, `/mnt/c/Users/x`; POSIX shells and the Glob and Grep tools,
  not PowerShell or cmd), a leak in f3a720f found on a real Windows 11 machine;
  `gci C:\*.py -Recurse`; cmd `dir/s` glued and the `dir /s` leaf rule above; `forfiles /s` (its
  `/p`, else the cwd) from Bash, cmd and PowerShell; `-Recurse:$false` is no recursion; the
  rg/fd/ag depth rule; the 64 KB cap. scan-guard.sh: `forfiles` joins the pre-filter's words, and
  an `-e...` option followed by 16 base64 characters starts Python too (an encoded script names no
  scan word). search_nudge.py: untouched.
- **Known gaps** (in the corpus as `known_gap`, reported, not failed). From failing open: a
  here-document's body, also one fed to a shell (`bash <<'EOF' ... EOF`, `sh -s <<EOF ... EOF`);
  the lines after a quoted `<<WORD` up to `WORD` (`grep -n '<<EOF' notes.md` then `find / -name x`
  on the next line; as in f3a720f); a dotted `dir /s` leaf whose variable is unset in the hook's
  environment (`%USERPROFILE%\codemap.py` with `USERPROFILE` unset); a command over 64 KB. Others:
  text piped into a shell (`echo "find / -name x" | bash`); paths from stdin
  (`echo / | xargs find`); paths built at run time (`F=/; find $F`, `find $(echo /)`); scans in
  other languages (`python3 -c "os.walk('/')"`); a root spelling with more than `..` after it
  (`find ~/proj/../.. -name x`); `robocopy C:\ NUL /L /S`;
  `Start-Process cmd -ArgumentList '/c dir /s C:\'`; .NET enumeration
  (`[IO.Directory]::EnumerateFiles('C:\', '*', 'AllDirectories')`); and two false blocks: Glob with
  a root `path` and a one-level pattern (`*` in `/`), and a here-document whose body has an odd
  quote (`cat > notes.md <<EOF`, `Don't scan the disk.`, `EOF`) followed by a commit message with
  `find / -name x` and a quoted `<<EOF` across two lines (refused in f3a720f too): the quoted
  `<<EOF` drops the lines up to the end of the input, so neither the text as written nor the text
  without bodies splits, and the token fallback sees `"find /`. A possible fix, not built: fail
  open when a here-document opener runs to the end of the input without its delimiter. The leaks in
  this list would each need the guard to evaluate or interpret more than one command's words. Hook
  gap (`hook_gap`): `f"in"d / -name x` is refused by the predicate but the sh pre-filter sees no
  scan word, so Python never runs; catching it would mean a regex with optional quotes between
  every letter of every word, for a deliberate obfuscation. Not in the corpus: a here-string to a
  shell (`bash <<< 'find /'`); a command over 64 KB (the cap; tested in the corpus test).
- **Version.** plugin.json 0.9.8 (the guard refuses more). README: the hook description names
  `eval`, `-EncodedCommand`, `iex`, `forfiles /s`, the depth rule, the 64 KB cap, the Git Bash
  spellings of a Windows home and that a here-document's body is text. Ceilings unchanged (no
  SKILL.md edit). [not verified on Windows] the new paths; synthetic hook input on Linux only.

### 22. Exact same-blocker brake, model check, bounded validation, doc self-check, record format (plugin 0.9.9)

Owner rule for this change: no added model token cost to a manager run (no new subagent, model
call or per-phase or per-round tool call; the manager SKILL.md and both briefs not longer in
words; ceilings unchanged; script output into context at most one short line, only when there is
something to say).

- **Same-blockers brake made exact.** The re-reviewer gets `Previous blockers` numbered as the
  last review numbered them (`B<n> <title>`) and answers each as `resolved` or
  `still present as B<k>` (its own blocker for that defect). `review-round.md`: the brake holds
  when every previous blocker is `still present as B<k>` and those cover all of the re-review's
  blockers; the ledger line keeps the numbered titles and gets `same` when it holds; an untagged
  line (an incomplete one) → titles compared as before. Cost: a few output tokens in a line the
  reviewer already writes; no extra call; the orchestrator matches tags instead of judging prose.
  SKILL.md untouched (the definition lives in `review-round.md`, read at every review step).
- **Model check.** `usage.py` takes `AGENT=MODEL` (several: `a,b`; subagents only, not
  `orchestrator`; `inherit` turns the check off). Both sides are lower-cased and lose a context
  suffix such as `[1m]`, a trailing `-YYYYMMDD` or `@YYYYMMDD` date and a provider prefix (up to
  the last `.` or `/` before the first digit). A versioned name must then equal the id or end it on
  a `-` boundary; a name with no letters is marked; an alias (no digit, such as
  `sonnet`) is a substring match. A suffix after the version, such as `-v1:0`, is marked (a false
  mark, never a false pass). When any request an agent ran used a model matching none of them, its
  `model` field ends in `!=MODEL` (the line keeps its 14 fields). `run-record.md` passes the
  strategy's model with each agent; `manager-retro` counts the marked agents per role and run. Cost:
  none in context (the line is appended to the record file in a Bash call that already runs). With
  the retro switch off there is no record and no `usage.py`, so the model is **not checked** in such
  runs. Tests: `scripts/test_usage.py` (`ExpectedModelTest`).
- **Bounded validation.** Implementer step 5 and the reviewer's validation: run commands under
  `timeout -k 30 1800` where `timeout` exists (the implementer: long probes too), a plan or project
  limit wins, exit 124 or 137 is a fail. The defaults (30 s grace, 30 min limit) are this change's
  choice. Without `timeout` the command runs plainly. A slow suite with no stated limit now fails at
  1800 s (exit 124); a project or plan sets its own limit to allow longer. Cost: four words in each
  command the agents already run. `timeout` does not kill a Windows process tree reliably (Git
  Bash's coreutils `timeout` signals the process it started, not necessarily the native children it
  spawned) [not verified on Windows].
- **Doc/record self-check** (retro evidence: 27 of 66 real blockers, 41%, were doc or record
  accuracy, in 6 of 7 projects; 49% of phases needed a second review). No equivalent rule existed
  (step 4 updates later phases "if facts require"; the vault brief covers pages a phase makes false,
  not lines it writes wrong). Implementer step 5, its own sentence before the final validation:
  check every plan, vault and doc line the diff changes against the code (so lines from before a
  rotation count too); fix misstatements. Cost: a few reads of lines the implementer just wrote,
  against a fix round (a cold resume plus a new review) it avoids. Failure signal: in later run
  records the doc/record share of blocker classes stays at 35% or more, or the implementer context
  median rises more than 10%.
- **Run-record format** (retro evidence: 3 of 6 records since 0.7.3 drifted: `193k`-style
  values, `?`, `1 fix`, tags with spaces, abbreviated verdicts, phase lines after the last
  summary). `run-record.md`: numbers are integers or `unknown`; `rounds` counts the phase's
  reviews; verdicts in full; blocker tags kebab-case without spaces; a phase line written after
  a `summary:` line is followed by a new one. Location, privacy rules and columns unchanged. The
  pre-0.8.3 column-name note moved out (the retro skill keeps it).
- **Hook Python lookup on Windows** (measured on a Windows 11 machine, idle: `ls -la` through
  `scan-guard.sh` ~650 ms at 0.9.7 and 0.9.8; `sh` start ~20 ms, `py -3` start ~57 ms; there
  `python3` and `python` are Microsoft Store stubs under `WindowsApps` that exit 9009). Not
  re-measured here: timing on Linux says nothing about the stubs; reasoned from the code, the
  wrappers ran both stubs before `py -3` [inference: the stubs cost most of the ~570 ms]. All six
  wrappers with the loop (`agent-paths.sh`, `codemap-commit-check.sh`, `codemap-rules-version.sh`,
  `codemap-search-nudge.sh`, `manager-context-watch.sh`, `scan-guard.sh`; their header comments say
  so) now try a `python3` or `python` whose `command -v` path has a `WindowsApps` folder
  (case-insensitive) only after `py -3`, and still try it last: a Microsoft Store Python is a real
  one there, so skipping it outright would leave such machines without Python. POSIX behaviour
  unchanged (a Python found elsewhere runs first, as before); the cost is one `command -v` in a
  subshell per candidate tried. No new files or caches. Tests: `hooks/test_wrapper_paths.py`
  (`WindowsAppsStubTest`: a sleeping, failing stub under a `WindowsApps` folder is never run when
  `py` works; a Store-style Python there still runs; a Python elsewhere runs first), POSIX only.
  [not verified on Windows] the timing gain.
- **Word and character counts** (`wc -w`, and `str.split()` / `len` as
  `hooks/test_manager_compaction.py` counts; before → after): manager SKILL.md 2,721 → 2,721
  words, 17,986 → 17,986 chars (untouched); code-map SKILL.md untouched (19,999 chars);
  implementer-brief.md 1,306 → 1,305 (`split` 1,326 → 1,325; ceiling 1,327); reviewer-brief.md
  1,325 → 1,324 (`split` 1,347 → 1,346; ceiling 1,347); review-round.md 559 → 556;
  run-record.md 1,156 → 1,153. The added rules are offset by tightening nearby text in the same
  files. manager-retro SKILL.md 1,391 → 1,420 (not read in a manager run).
- **Version.** plugin.json 0.9.9. README: the same-blockers brake, the model mark in the `usage`
  lines and the hooks' Python order.

### 23. Rare-path text moved out of always-loaded SKILL.md bodies (plugin 0.9.10)

Owner rule for this change: no added token cost. Only text whose path is rare in a normal run
(first-time setup, Python install, hook install/uninstall, migration or adoption, error recovery,
rarely used commands) moved, verbatim (re-wrapped; an antecedent such as "as above" named), into a
`references/` file read only then; each moved block left one pointer naming its trigger and file.
No rule was reworded, weakened or deleted; no read was added to a normal run.

- **Character counts** (`len`, as `hooks/test_manager_compaction.py` measures; before → after):

  | SKILL.md | before | after | saved |
  |---|---|---|---|
  | code-map | 19,999 | 9,108 | 54.5% |
  | manager | 17,986 | 17,587 | 2.2% |
  | self-training-skills | 13,720 | 12,935 | 5.7% |
  | create-vault, living-plan, manager-retro | 7,302 / 8,317 / 9,123 | unchanged | 0 |

- **code-map: moved.** Where it writes (detection order, map locations, `.codemap.json` rules) →
  `references/layout.md` (no `.codemap.json` yet, `detect`, first `build`, `build --redetect`, a
  refused `build`); the Python install offer → `references/python-install.md` (no Python);
  Setting it up and **The rules block** with its template → `references/setup.md` (setup, a block
  written by hand, an outdated block); both commit hooks' detail → `references/commit-hooks.md`
  (turning one on or off, a commit one stopped); the search nudge's state, switch, failure modes,
  what counts as broad and known gaps → `references/search-nudge.md` (turning it off, a search it
  blocked or allowed unexpectedly). **Kept:** what the map holds and how it is built, the command
  resolution and every command, the nudge's scope and one-time block, Rules, In the manager.
- **manager: moved.** "No living plan" / "work not split into phases" → `references/no-plan.md`
  (read only at step 0 when there is no plan or the work is unsplit); a refused or blocked landing,
  with the branch-protection line from **GitHub CI is not a gate** →
  `references/refused-landing.md` (read only when a landing is refused or blocked). Not into
  `landing.md` (read at every phase's landing) or `establish-state.md` (read at step 0, after each
  compaction, and again at loop steps 1 and 2 when the default head moved): there the moved text
  would be paid more than once per run. Both files are byte for byte as at 0.9.9 (`landing.md`
  2,192 chars, `establish-state.md` 5,127). **Kept, normal path or a tested invariant:**
  ground rules, subagents, model strategy and run marker, step 0 items, every loop step, brakes,
  owner decisions, talking to the owner, run record, stop conditions. 15% was not reachable: the
  body is already mostly invariants the tests pin to SKILL.md and pointers; the remaining rare
  branches (the designated-branch exception, the brake-reset exception, the fix-round fallback
  when the implementer can't be resumed) are either pinned invariants or too short to save more
  than their pointer costs.
- **self-training-skills: moved.** Adopt mode → `references/adopt.md`.
- **Ceilings.** code-map SKILL.md 20,000 → 9,500 (new size rounded up to the next 500); manager
  SKILL.md stays 18,000 (17,587 rounds up to 18,000). New test `test_rare_path_pointers_resolve`:
  every `references/<file>` code-map and self-training-skills name exists, and every file there is
  named. `test_codemap.py` reads the rules-block template from `references/setup.md`.
  `brief-code-map-setup.md` names the template's new file.
- **usage.py.** `expect()`: with `=` but every name (`inherit` aside) empty after normalising
  (`a1=`, `a1=,`, `.`, `[1m]`, `-20260101`), the line is marked `!=unknown` instead of the check
  being turned off (`ExpectedModelTest.test_names_that_are_empty_once_normalised_are_marked`).
  Header, entry 22 and the test docstring say "a name with no letters is marked"; the header's
  141-character line re-wrapped to 100 columns.
- **Version.** plugin.json 0.9.10.

### 24. code-map `impact` and budgeted `query` (plugin 0.9.11)

Owner rule for this change: no added token cost. Both commands run only when an agent asks for
them: no hook, brief or skill step calls them, and `implementer-brief.md`, `reviewer-brief.md` and
manager SKILL.md are untouched (whether reviewers should use `impact` will be decided from eval
data, not now).

- **`impact <path>...` / `impact --base <sha>`** (`--depth N`, default 2). What: per file, its
  importers (direct, then each further level, each file once), the test files among them and
  those named after it, and per top-level definition the other files of its language naming it.
  Why: before editing a widely used file, one call answers "what does this touch" that otherwise
  takes several `grep`s. Built on the existing scan (`scan`'s importers, `is_test`, `TEST_AFFIX`,
  `changed_files`, `code_part`); no new parser. Import-based lines and the name-based
  `referenced` lines (a whole-word match, Python outside strings and comments; may include false
  matches) are marked as such in the first line. At most 60 lines, lists capped.
- **`query <term> --budget N`.** What: the same items as `query`, ranked (exact name or path
  match first, then by import in-degree or inbound vault links, then `query`'s order) and kept
  while the output stays within about N tokens (characters / 4, said in `--help`); a cut ends
  with `… <k> more (raise --budget)`. Why: a broad term's `query` can run to hundreds of lines.
  Without `--budget` the output is byte-identical to 0.9.10 (golden test).
- **Cost argument.** Nothing new is loaded or run by default. code-map SKILL.md grows by three
  lines naming the commands and when they help, with a pointer: 9,108 → 9,347 chars (ceiling
  9,500 kept). The detail is in `references/impact-budget.md`, read only when using them.
- **Measured output** (this repository, 34 source files): `impact` on
  `plugins/manager-plugin/skills/manager/scripts/usage.py` 17 lines, 2,757 chars (about 690
  tokens); `query hook --budget 300` 1,193 chars against 2,876 without `--budget`. On a large
  open-source Python clone (7,104 tracked files): `impact` on a widely imported utility module
  15 lines, 3,365 chars, 4.8 s; `query model --budget 300` 30 lines, about 1,200 chars, against
  419 lines and 20,472 bytes without it, 2.1 s (the scan dominates; the same as plain `query`).
- **Tests.** `skills/code-map/scripts/test_impact.py`: a fixture with a chain a → b → c, another
  importer of c and a test; `impact` on c lists b, a and the test; `--depth 1`; `--base`;
  each dependent once; the budget cut keeps the exact match and prints the more-line; `query`
  without `--budget` equals the 0.9.10 output (golden).
- **Follow-ups from the 0.9.10 review.** Manager SKILL.md ceiling 18,000 → 17,600 (17,587, this
  change doesn't grow it). `test_moved_rules_exist_exactly_once` also pins one key sentence of
  each file moved in 0.9.10 (code-map `layout.md`, `python-install.md`, `setup.md`,
  `commit-hooks.md`, `search-nudge.md`; manager `no-plan.md`, `refused-landing.md`;
  self-training-skills `adopt.md`), counted across every skill's SKILL.md and references.
  create-vault SKILL.md names `references/setup.md` for the rules block (7,302 → 7,299 chars).
  Entry 23's two lines over 100 columns are wrapped.
- **Version.** plugin.json 0.9.11. README names both commands.

### 25. Lessons need a verifier outcome; confidence and staleness (plugin 0.9.12)

Evidence: SkillsBench (arXiv 2602.12670) measured curated skills at +16.2pp and self-generated,
unverified ones at -1.3pp; claude-reflect keeps a confidence and a decay so stale lessons get
pruned. Owner rule for this change: no added token cost.

- **Already there.** `label` (`owner-reported` / `observed` / `sourced` / `hypothesis`) and
  `evidence` columns; `check` required a rule's lesson ids to exist and not be `retired`;
  `evidence-rules.md` said a single record is never a rule and a `sourced` lesson may seed one at
  creation. Not enforced: a `hypothesis` (or any lesson without a verified outcome) could back a
  rule, and nothing aged.
- **Verifier outcome.** A rule's lesson must not be a `hypothesis`, and its `evidence` must cite a
  records row as `<YYYY-MM-DD> <context>: <outcome>` (`pass`, `changes-required`, `failed`,
  `owner-good`, `owner-bad`) that the records hold, or an owner verdict `owner: "<words>",
  <date>`. A cited row the records lack is a problem. A `sourced` lesson may back a rule without
  one only until the first training (the changelog has only its creation entry), so Create still
  passes `check`.
- **Columns.** `confidence` (`high`: 2 or more independent outcomes, i.e. distinct date and
  context, or an owner verdict; `medium`: one; `low`: none) and `last-confirmed`
  (`YYYY-MM-DD` or `unknown`). Append-only keeps one stated exception: a status change or a
  re-confirmation may update these two fields in place.
- **Stale.** `check` (as a `note:`) and `stats` print one `stale lesson L<n>` line per `active`
  lesson last confirmed more than 90 days ago (`--stale-days`) or with more than 20 records rows
  dated after `last-confirmed` (`--stale-uses`); in `stats` too each such line carries the `note:`
  prefix; Train puts it to the owner (keep, re-confirm, retire). Never auto-retired; no line when
  nothing is stale; `due` is unchanged. A `last-confirmed` later than
  today is a problem (it would hide the lesson from staleness).
- **Migration.** A five-column table still works (read as `low` / `unknown`, one `note:` line);
  its evidence gaps (a rule's lesson without a verifier outcome, a cited row the records lack)
  are `note:` lines, not problems, until it is migrated (a `hypothesis` behind a rule is a
  problem either way). `check --migrate` adds the two cells right after each line's last pipe,
  filled from the evidence and the records; it splits on `\n` only, and every other byte stays
  (test). A row with other than five cells is refused, nothing written.
- **Cost argument.** No new model call, subagent, hook or step: the work runs inside `check` and
  `stats`, which Create and Train already run. Output grows only by the stale and old-table lines.
  self-training-skills SKILL.md 12,935 → 12,927 chars (the detail is in `lessons-format.md` and
  `evidence-rules.md`); manager SKILL.md and the briefs untouched.
- **Tests.** `test_skilltrain.py` `LessonEvidenceTest`: old and new tables, bad and future cells,
  confidence rules, a rule citing a hypothesis or an unverified lesson, a cited row the records
  lack, the `sourced` seed window, staleness by days and by uses (and the options), no line when
  nothing is stale, old-table gaps as notes and migrated ones as problems, the changelog
  problems' place, migration byte-identical (CRLF, trailing whitespace, U+2028 / NEL / FF / RS
  in a cell, idempotent) and a refused migration.
- **Also.** code-map `references/impact-budget.md` paragraph rewrapped to 100 columns (same
  words). plugin.json 0.9.12; README names the verifier outcomes and stale lessons.

### 26. Weakened-guard flags, invisible-Unicode check, hook silence test (plugin 0.9.13)

Source: ideas from reading a public MIT-licensed plugin repository; our own code, nothing copied.
Owner rule for this change: no added token cost.

- **Weakened-guard flags in `changed`.** What: after the pointers (and after their 60-line cap), a
  `possible weakened guards (approximate, never a filter):` section, printed only when something is
  found, at most 8 lines and then `… <k> more` (9 are all shown, as the 60-line cap cuts only two or
  more), each `<kind>: <path>: <reason>`, sorted by kind then path: a test file (`is_test`) deleted,
  renamed, moved, or moved and renamed (git's rename detection; also when the new name is no longer
  a test's); more lines with a skip marker (`@unittest.skip`, `skipTest(`,
  `pytest.mark.skip`/`xfail`, `@Disabled`, `t.Skip(` anywhere; `.only(`, `xit(`, `xdescribe(`,
  `.skip(` in test files) or a suppression (`noqa`, `type: ignore`, `eslint-disable`, `@ts-ignore`,
  `nolint`, `pragma: no cover`) than before; a test file with fewer `assert` / `expect` lines; an
  edited, added or deleted lint, format, type-check, test or CI configuration file, and a
  `pyproject.toml` whose `[tool.*]` tables differ. Not counted (fix round, to cut noise):
  conditional skips (`skipIf`, `skipUnless`, `pytest.mark.skipif`, a skip call after an `if` on its
  line or in a block opened by `if`, `elif`, `else`, `except`, `catch`, `case`, `when` or `unless`,
  found by indentation; known gaps: the condition is not read, so `if True:` and `skipIf(True, ...)`
  are not counted either), a `noqa` whose only code is E402 (`# noqa: E402, F401` still counts), and
  assert lines in a test folder's data files (only languages the map parses count as test code; the
  simpler of the two options, chosen). Why: the reviewer already runs `changed`; a weakened test or
  check is easy to miss in a long diff. Counts compare the two versions of each file (a moved line
  counts for nothing); prose files and files that may hold secrets are not read. Without a finding
  the output is byte-identical to 0.9.12 (golden test; the 0.9.12 range of this repository gives the
  same bytes with both versions).
- **Invisible-Unicode check.** What: `skilltrain.invisible_chars` (stdlib) finds U+200B-200D,
  U+2060-2064, U+FEFF, U+202A-202E, U+2066-2069, U+115F, U+1160, U+3164, U+FFA0, U+FE00-FE0F,
  U+E0000-E007F and U+E0100-E01EF. Always allowed: a BOM as a file's first character (`read_rel`
  already accepts one) and a ZWJ between two emoji (the next character, and the previous one past
  variation selectors and skin-tone modifiers, in the emoji blocks). `strict=True` (the default)
  allows nothing else: `test_invisible_unicode.py` uses it on every text file of the plugin and the
  repository's root `*.md` and `docs/` (file:line:col and the code point). `skilltrain.py check`
  uses `strict=False`, so existing skills don't newly fail (as 0.9.12 kept old tables working): it
  also allows a variation selector right after an emoji or a keycap base (`0-9#*`, then U+20E3), a
  ZWNJ / ZWJ inside a non-ASCII word (the character before it, past any combining marks such as a
  Devanagari virama, and the one after it are non-ASCII letters: Persian, Indic scripts), and the
  tag characters of the three RGI subdivision flags, England, Scotland and Wales, as exact sequences
  (review fix: any other tag payload is a problem). Per line of SKILL.md, lessons.md and the records
  file it then prints a problem (exit 1) when the line holds a bidi control (U+202A-202E,
  U+2066-2069) or a tag character outside those three flags, else a `note:` line (exit unchanged);
  never stripped. Why: such characters can hide instructions from whoever reviews a skill.
- **Hook silence test.** `hooks/test_hook_silence.py` runs every command hooks.json registers as
  Claude Code does (`sh -c`, CLAUDE_PLUGIN_ROOT set), for every matcher alternative: an input no
  guard acts on gives no stdout, no stderr, exit 0; each hook whose script can exit 2
  (prefer-plugin-agents, scan-guard, search nudge, commit check) blocks one input with exit 2 and a
  message, and so does the search nudge's skills-first branch (a marked skill, a search of
  `.claude/skills`), checked at run time so its `%`-formatted text is too; no probe output (none
  with a `%s` left in it) and no blocking message in the hook sources names an environment variable,
  config key, settings file or off-switch wording. The prompt marker `[general-purpose: <reason>]`
  is a per-call escape with a stated reason, not a setting: allowed. Out of its scope and unchanged:
  the git pre-commit hook (`codemap.py pre-commit`, installed by `install-hook`, no hooks.json
  entry) tells the agent to "commit with --no-verify" when a tracked input isn't readable (sparse
  checkout); for the owner to decide.
- **Cost argument.** Nothing new runs by default and no always-loaded text grows: the flags are
  output of `changed`, only when found; the Unicode check is a test and a `check` problem; the
  silence test is a test. code-map SKILL.md stays at 9,347 characters (the bullet names
  `references/changed-flags.md`, the detail is there); self-training-skills SKILL.md, manager
  SKILL.md, the briefs and the hook scripts are untouched; ceilings unchanged.
- **Noise, measured** on the 7 merges to main d73d0bb ... f024a60 (each against its first parent):
  before the fix round 4 ranges showed the section (2, 2, 2 and 10 lines, all justified: `# noqa:
  E402` imports, `skipIf` / `skipUnless`, `skipTest` under an `if` or `except`); after it none does.
  The planted fixture still gives all eight findings.
- **False-positive risks.** A justified change is flagged too: a test moved with its code, a `noqa`
  with another code, a CI edit that only adds a job. Splitting a test file into two gives `asserts`
  on the file the tests left (they moved, they didn't go). A test folder's data file in a language
  the map parses (a `.py` or `.js` fixture) still counts as test code. `.skip(` / `.only(` in a test
  file may be an unrelated method; any line holding `assert` or the word `expect` counts (comments,
  `assertion`); an assert rewritten as one line from two counts as removed. Misses: a weakening the
  markers don't name (an early `return`, a loosened tolerance, a check removed from a non-test
  file). The emoji test is a block range, not Unicode's emoji property.
- **Also.** TODO 25 and the skilltrain usage docstring: a lesson is stale with more than 20/M
  records rows dated after `last-confirmed`; `stats` stale lines carry the `note:` prefix too. The
  `check` docstring says old five-column tables report evidence gaps as notes. plugin.json 0.9.13;
  README names the weakened-guard section and the Unicode check.

### 27. Zero-test guard, plan and vault checks, trigger-clause test, failure streaks (plugin 0.9.14)

Source: ideas from reading public agent frameworks (MIT / Apache-2.0); our own code, nothing
copied. Owner rule for this change: no added token cost, with one owner-approved exception (the
zero-tests sentence in both briefs).

- **Zero tests is not a pass.** What: one sentence in the validation step of both briefs: a test
  command that exits 0 while its log shows zero tests run (`Ran 0 tests`, `no test files`,
  `collected 0 items`, `# tests 0`, `0 passing`) is a fail. Why: a wrong discovery folder or a
  filter that matches nothing exits 0 and reads as green. Cost: 30 words per brief (as the test
  counts them, `str.split()`: implementer 1,325 → 1,355, ceiling 1,327 → 1,357; reviewer 1,346 →
  1,376, ceiling 1,347 → 1,377), the only ceiling change; no other brief text was reworded. A test
  pins the sentence in both, once each. No helper script: it would need its own brief text. False
  positives: a log that prints one of these strings for a sub-suite while others ran (the agent
  reads the log, so it can tell).
- **`plan.py check` warnings.** What: after the existing warnings, one line per hit with the phase
  id and the field: a placeholder left in a required field (`<` then `...` or a letter up to the
  next `>`, outside backticks only; anywhere `TODO` / `TBD` as words of their own, not inside a path
  such as `docs/TODO.md`, `???`, `NEEDS CLARIFICATION`), and a `Validation` command piped into
  `tail`, `head`, `grep`, `less` or `tee` while the field names neither `pipefail` nor `PIPESTATUS`.
  Exit code unchanged. A `<...>` slot inside backticks is a command template (`git show <sha>`), not
  flagged (review fix: all 9 first-round hits on this repository's plan were such templates; it now
  prints what 0.9.13 printed); documented in `references/plan-template.md` (SKILL.md unchanged).
  Why: a plan handed to the manager with a slot still open, or a validation whose failure a pipe
  turns into exit 0. Cost: output only when found; a plan without hits prints the same bytes. False
  positives: a bare HTML tag (`<br>`) counts as a slot; a `TODO` word in prose is flagged; a pipe
  inside a quoted string counts. Misses: a slot left inside backticks.
- **Dead sources in vault pages.** What: `codemap.py check` (not `--quiet`, not the map) prints
  `warning: dead source <page>:<line> -> <path> (no such file)` after the broken-link warnings, at
  most 20, only when any exist. Cited: a markdown link to a non-page file, and a code span with a
  `/` that ends in `/` or in a file extension, only when the path's first part is an entry of the
  repository root or a folder name anywhere in the tracked tree (review fix: the first version
  checked every such path, and 8 of 9 probe hits named other repositories' files). Skipped: fenced
  code blocks, absolute paths, placeholders (`<`, `>`, `*`, `{`, `$`, `...`, `path/to/`, a part
  named foo, bar or baz or holding "example"). A path is alive when it is on disk from the root, or
  a tracked path is it or ends with "/" and it (`scripts/<name>.py`, a path relative to a skill
  folder), or, for a folder, holds it. Why: vault pages cite their sources, and a moved file leaves
  a stale citation nobody checked. Cost: a `check` warning only; the map, `build` and `--quiet` are
  unchanged; a clean vault prints the same bytes (golden test, also run against 0.9.13's script).
  Probe (`check --vault docs` on this repository, which has no vault): 9 lines with the first
  version, 1 now, the real one: the retired trainer template under a skill's references folder,
  cited in item 15 (0 false hits). False positives: another repository's file under a folder name
  this tree also has; misses: a bare file name, a code span without an extension, a moved file whose
  name still ends some tracked path.
- **Trigger-clause test.** `hooks/test_trigger_clauses.py`: every model-invoked skill's description
  keeps "Use when" / "Use for" (`disable-model-invocation: true` skills are exempt), every agent's
  its "Use ..." / "Used only when" clause. A test only.
- **Failure streaks.** What: `usage.py SESSION --streaks` adds after each `usage` line one
  `streaks | agent | failure streaks | longest | tool` line: runs of 3 or more consecutive tool
  calls with the same tool and input (compared as sorted JSON), each with an `is_error` result; the
  tool name only, never the input. Off by default (normal output byte-identical); no run asks for
  it. Why: a measure of agents retrying the same failing call, for `manager-retro`. Measured on 59
  local subagent transcripts and one orchestrator: 63 error results, 0 streaks. False positives:
  none known; misses: an error reported in a result's text without `is_error`, a retry with a
  slightly changed input. Across a session's several project folders the calls are taken folder
  by folder, not by time.
- **Also (0.9.13 review follow-ups).** `NOQA_IMPORT` is matched at the line's first `# noqa` and
  exempts only when no further code (letters then digits) follows E402 with any separator
  (`E402 F401`, two spaces, a tab, `F401 # noqa: E402` now count; `(after the path setup)` stays
  exempt; a remark holding e.g. `py3` counts too: a false mark, never a false pass).
  `skilltrain.py check` scans the worker skill's `references/*.md` too (same non-strict rules).
  The joiner rule also allows a ZWNJ / ZWJ before a non-ASCII combining mark on a non-ASCII letter
  (Sinhala touching form) unless an ASCII letter or digit follows the marks, and a ZWJ after a
  virama (combining class 9) on a non-ASCII letter at a word's end (Malayalam old-style chillu);
  ASCII-adjacent joiners stay notes.
- **Pre-commit `--no-verify` advice: checked, unchanged.** With the git pre-commit hook installed
  in a sparse checkout missing one map input, the map built in a full clone of the same commit,
  copied in and staged, a plain `git commit` is still stopped: a staged map page makes the hook
  rebuild, and the missing input stops it before the build. Dropping the `--no-verify` advice
  would need a logic change (e.g. accept staged map pages that match a build from the index), so
  the message and `references/commit-hooks.md` are left as they were; for the owner to decide.
- plugin.json 0.9.14; README names the new warnings, the `references/` scan and `--streaks`.

### 28. Reviewer calibration eval, built, not run (plugin 0.9.15)

Source: the method of cross-review (lploc94): planted bugs, decoys that look wrong but are
correct, clean diffs, blind grading. Our own synthetic cases and code; nothing copied (its
license is unclear). Owner rule: built and tested only; the paid run waits for the owner's budget.
No change to the reviewer, its brief, the manager skill or a hook; nothing runs in a normal run.

- **Where.** `plugins/manager-plugin/evals/reviewer-calibration/`: 20 `claude plugin eval` cases
  `rc-01` to `rc-20` in a shuffled order (`case.yaml`, `prompt.md`, `scaffold.sh`, `graders/`),
  the shared `fixture.sh`, `score.py` and `run.py`. Nothing in a case (description, the one shared
  tag, prompt, file names, commit messages, branches) tells its kind. The answer keys are
  `evals-keys/reviewer-calibration/<case>.json` at the repository root, outside the plugin folder;
  only they map an id to its kind (the labels below are their `name` fields). Each scaffold builds a tiny standard-library Python repository (66-101
  lines in all): rules, a one-phase plan with acceptance criteria (`plan.py check` passes), the
  base on `main`, pull request #1's candidate on `phase/P1` (round 2: two commits), a local mirror,
  the checkout on the candidate; the local git config records the absolute path of the plugin's
  reviewer brief (`eval.reviewerbrief`), since a fixture without a code map gets no plugin start
  line to find it from. The session sends one `manager-plugin:reviewer` the reviewer
  brief's dispatch and relays its answer. Validation (`python3 run_tests.py`) exits 0 at every
  candidate, so no planted bug is caught by the tests alone.
- **Cases** (key labels; the id of each is in its key). Planted, L1 obvious: `l1-off-by-one` (`page_count` = `total // size + 1`),
  `l1-wrong-operator` (`>` where the acceptance says at least). L2 logic: `l2-empty-input`
  (`mean([])` divides by zero), `l2-wrong-condition` (a 429 skips the attempt limit). L3
  cross-file: `l3-caller-not-updated` (`load(paths)`, `cli.py` still passes one string),
  `l3-contract-change` (`find` raises `KeyError`, `service.record` expects None). L4 doc or
  record drift: `l4-readme-drift` (README default 20, code 10), `l4-plan-drift` (a change-log
  line claims accent folding). Guard: `weakened-test` (the failing test skipped as flaky, the
  0.9.13 flags), `zero-tests` (tests renamed out of discovery: exit 0, `Ran 0 tests`, the
  0.9.14 rule). Decoys, comment-free: `decoy-fallthrough` (chained `if`s reassigning the role),
  `decoy-guarded-none` (`match and match.group(1)`), `decoy-for-else`,
  `decoy-ceil-idiom` (`-(-n // size)`). Clean: `clean-clamp`, `clean-retry`,
  `clean-readme-option`, `clean-slug-limit` (the last three are the right twins of an L2 and
  both L4 cases, same base). Round 2, with `Previous blockers`: `round2-fixed` (a real fix),
  `round2-unfixed` (0 refused, 65536 still accepted).
- **Graders.** In the run (free, regex and `tool_used`): a reviewer got this candidate, the final
  message holds a verdict line, and the trace names none of `reviewer-calibration`, `evals-keys`,
  `evals-results`, `evals/results`, `score.py`, `test_reviewer_calibration`, `answer.json` (the
  brief, the reviewer agent and the workspace hold none of them; a test checks it). No grader on
  the expected verdict: a case's graders would tell it.
  `score.py` (deterministic, blind; reads `aggregate-result.json`, each run's trace, and the keys):
  a run with an `error`, a failed `blind`, `reviewer-dispatched` or `answer-relayed` grader, or a
  missing trace is INVALID, listed with its reasons, left out of every total, and the exit is 1.
  Of a valid run it reads the reviewer's own answer (the Agent tool result, else the final
  message), its `VERDICT` and blockers (`B<n>.`, `-`, `1.` entries; `Blockers:` or a heading
  without a colon, `## Blockers`, `**Blockers**`; markdown bold, `none`, `no blockers`, `n/a` or a
  lone dash on the heading or the next line is no blocker). Planted: found when a blocker holds
  one of the key's `alone` terms (guard cases only: `Ran 0`, `0 tests`, `skip`, ...), or names a
  key file and a line in the key's range (`file:12`, `file:10-14`) or a key term. Terms are whole
  words, never a cited line number (`README.md:20` holds no `20`), and specific to the bug, so a
  wrong fault on the right file is missed; the tests hold a wrong and a right blocker for each
  loose or strict term found in review. Decoy or clean: any blocker or CHANGES REQUIRED is a false
  alarm. Round 2: the fixed case is right when it is accepted (PASS or PASS WITH NOTES, with no
  blocker); the unfixed case is right when it is refused (CHANGES REQUIRED). Report: per run,
  recall per level and overall, false-alarm rate (decoys, clean, both; runs without a verdict
  apart), round-2 right, no-verdict and invalid runs, cost (`costUsd`) and tokens (input, cache
  read, cache write, output; all agents and the reviewer's share, each message id once). It also
  writes `audit.md` beside the result: per run and blocker, the case, kind, verdict, the blocker
  (200 characters at most), the match decision with the term or line that matched, and the
  INVALID reasons. Keyword matching is never exact: the pilot's numbers are to be read with it.
- **Runner.** `run.py --max-cost-usd USD` (required) `[--model sonnet|opus] [--runs N] [-j N]
  [--case GLOB] [--dry-run]`, defaults Sonnet, 1 run, `-j 1`: `claude plugin eval` with `--tag
  reviewer-calibration --ablation none --scaffold --no-publish --keep-temp --allow-tools Agent
  Bash ToolSearch --max-cost-usd` (the CLI's hard ceiling, checked before each run) `--output-dir
  evals-results/<UTC time>` (repository root, git-ignored), then `score.py`. `--keep-temp`: in
  2.1.332 each run's `finally` removes its sandbox (`claude-eval-XXXXXX/`, `out/trace.jsonl`
  included) unless the run errored, so without it every run would be scored without a trace. After
  the eval run.py copies each trace to `traces/<case>-<n>.jsonl` in the result folder, points the
  result's `tracePath` there (the old path kept as `keptTracePath`) and removes the kept sandbox
  roots the result names (never by glob, without running git inside them). Before launching it
  refuses (exit 2) a repository or `TMPDIR` path holding a blind string, and warns when the
  repository is not under `$HOME`. It exits non-zero when the eval or `score.py` does. No
  `--trust-plugin`: the first run asks to trust the plugin interactively. The README's command
  for the invariant cases now names their tags, so it leaves this suite out.
- **Estimated tokens per run** (one run of the 20 cases; not measured, estimated from fixture size
  and `usage.py` on this repository's local reviewer transcripts): the 33 reviewer subagents of
  one local session took 6-49 requests, 89k-2.9M cache read, 4-44k output, 22-134k context at
  return; the smallest diffs (6-10 requests, 89-142k cache read, 14-20k cache write, about 4k
  output) are the nearest to these fixtures. So per case about 150-250k cache read, 20-30k cache
  write and 4-8k output for the reviewer, plus 50-100k cache read and about 20k cache write for the
  session; for the suite about 4-7M cache read, 0.8-1M cache write and 0.1-0.2M output tokens.
  At Sonnet list prices (assumed: 0.30 / 3.75 / 15 USD per million for cache read, cache write,
  output) about 0.25-0.5 USD per case, 5-10 USD a run; Opus (assumed 0.50 / 6.25 / 25) about
  1.7 times that. The one
  measured manager case (README, Sonnet, 23 turns) cost 0.31 USD. Unknown until the pilot.
- **Pilot** (1 run, Sonnet, capped; from the repository root):
  `python3 plugins/manager-plugin/evals/reviewer-calibration/run.py --max-cost-usd 15`
  (`--dry-run` first prints the exact `claude plugin eval` command; read the numbers with
  the result's `audit.md`). Start smaller with
  `--case rc-01` (one case; the CLI's glob takes `*` and `?`; pick ids from the keys).
- **Tests (free).** `evals/test_reviewer_calibration.py`: the mix, the keys outside the plugin,
  no kind hint in any case and a shuffled order, the blind pattern absent from the prompt, the
  briefs, the reviewer agent and every workspace, every case valid in the `test_evals.py` format
  and tagged for this suite only, one prompt apart from its commits and previous blocker and
  naming no answer, the graders; every scaffold run twice (same SHAs), the prompt's commits, a
  clean tree, under 150 lines, no key in the workspace, the plan check, validation exit 0 (0 tests
  only in the zero-tests case), each key's probe failing exactly at the planted and unfixed
  candidates, each key's lines holding its marker; `score.py` on hand-written answers (found by
  line and by term, markdown answers and headings, wrong faults on the right file missed, right
  blockers in other words found, missed, no verdict, false alarm, round 2), on a result with its
  trace, on invalid runs (each reason, exit 1) and the audit table; `run.py`'s command with
  `--keep-temp` and its required ceiling, the trace copy and sandbox removal on a fake result
  tree, the path checks, and its exit code. `test_evals.py` leaves the suite out of its invariant
  checks.
- **Limits.** The `aggregate-result.json` shape (`cases[].arms.with[]`, `costUsd`, `tracePath`,
  `error`, `graders[].passed`) and the sandbox clean-up are read from the 2.1.332 CLI, not from a
  run. The term match is approximate; the audit table is there to check it by hand, and the probe
  and line markers keep the keys true to the fixtures. Residual risk, from a static reading of
  the 2.1.332 sandbox builder (not an observed run): Bash's `denyRead` covers the operator's home,
  the plugin folder's parent, the system temp folder and similar, and the Read tool is held to the
  allowed tools and the eval folder's deny, so a checkout under home keeps `evals-keys/` and
  `evals-results/` unreadable. The real risk is a checkout outside home and outside the temp
  folder, where the repository root, keys included, may be readable through Bash; run.py warns
  then. The blind strings, traced statically the same way, do not appear in an honest run; only a
  checkout or `TMPDIR` path holding one would trip them, and run.py refuses to launch then.
- **Also (0.9.14 review follow-ups).** `test_usage.py`: `StreakTest` and its helpers above the
  `__main__` guard. Item 27: brief word counts as the test counts them. `test_invisible_unicode`
  `test_reference_files_are_checked_too` routes its files in `## Knowledge`, so the clean skill
  exits 0 and the exit 1 comes from the payload. `skilltrain.py check` scans nested
  `references/**/*.md` for invisible characters too (the routing already walks them).
- plugin.json 0.9.15 (the nested scan changes `skilltrain.py check`; the eval alone would not need
  it); README: the calibration suite, the tagged invariant command, `references/**/*.md`.

### 29. Calibration runner: portable trace paths (plugin 0.9.16)

- **What.** `run.py collect()` wrote the copied trace's relative path with `os.path.join`, so on
  Windows `aggregate-result.json` held `traces\rc-01-1.jsonl` and
  `test_collect_copies_the_traces_and_removes_only_the_named_sandboxes` failed. It now writes
  `traces/<case>-<n>.jsonl`, which `score.py` and Windows both read.
- **Why.** Found by the first Windows run of the free checks before the paid pilot (native
  Windows, Git Bash, CLI 2.1.330); the suite's stop rule held the pilot back. No other Windows
  failure in the six unit suites, `plugin validate` or the smoke runs.
- **Cost.** None: one string, in a script run only by hand.

### 30. Calibration runner: Windows attempts and the first pilot (plugin 0.9.17)

- **What.** `run.py` gains `--trust-plugin` (passed on to the eval), refuses to launch on Windows,
  falls back to `expanduser("~")` when `HOME` is unset, and opens file modes as well as folder
  modes before removing a kept sandbox. README and the docstring say so.
- **Why.** Two Windows attempts (native, CLI 2.1.330) spent nothing and found four things. The
  eval asks for trust only in a terminal and otherwise exits with an error. PowerShell's `bash`
  is the WSL launcher, so the scaffold failed. From Git Bash the scaffold passed, but Claude Code
  refused the session: no Bash sandbox on Windows, and folder modes do not restrict reads there.
  Clean-up failed on git's read-only objects.
- **Pilot.** One case (rc-01, Sonnet, Linux, CLI 2.1.332, checkout under `HOME`, run as root),
  `--max-cost-usd 2`.
  - Result: score 1.00, 0.13 USD, 26 s. The reviewer was dispatched with the real brief and ran
    the probe. It returned CHANGES REQUIRED with two blockers. `score.py` matched the first
    (found, L3); the second was an extra missing-test blocker.
  - Trace and clean-up: copied, and the sandbox was removed. No blind string; the init event
    lists one manager-plugin, the one under test.
  - Tokens: `score.py` summed the assistant events' usage, which under-counts output (their
    snapshots are not final) and misses the reviewer's last message: the pilot printed 952
    output tokens, 68 of them the reviewer's, against 2895 in the result's `modelUsage`. It now
    reads the final `result` event (`modelUsage` for the whole session; the reviewer is that
    minus the result's `usage`, the main thread's share), the old sum only as a fallback.
    Grading never used tokens.
  - As root the harness could not seal the kept sandbox: a step after the run, warning not to
    run git in it. The Bash sandbox's read denials are bwrap mounts, which hold under root too;
    only closures by file mode do not.
- **Cost.** None for normal runs. One short case cost 0.13 USD, so a 20-case Sonnet run is about
  3-5 USD, maybe up to about 8 with round-2 and larger cases (from one case only).
