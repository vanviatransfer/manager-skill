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
- Still open (0.9.0): the manager skill's size; hooks around compaction; an orchestrator
  context-size hook; real token accounting; a plan validate/extract script; a reviewer "changed"
  code-map command; plugin evals.
