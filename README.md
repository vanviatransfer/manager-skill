# manager-skill

A Claude Code plugin with six skills:

- **`living-plan`** — writes a project's living plan: goal, scope, binding decisions, phases sized
  for one PR each (with acceptance criteria and validation), and open owner decisions. Its
  `plan.py` (standard-library Python) checks the plan before its PR: every phase id used once,
  every `Depends on` naming phases of the plan (or `none`), no dependency cycle, every phase with
  its seven required lines, and a warning when two phases that are not done and don't depend on
  each other name the same path in their scope.
- **`manager`** — runs that plan to completion.
- **`create-vault`** — creates a project vault in `docs/vault/`, or adopts or refreshes an existing
  one: short linked pages of durable facts about the code (index, glossary, decision records, topic
  pages), each with its sources and a `Verified` line, landed through a reviewed PR. The plan's
  phases point to the pages they need, and the manager's implementers keep those pages current in
  their phase PRs. The vault holds durable knowledge about the code; progress and history live in
  the plan and git. In every mode the same PR also sets up the code map and the rules block (below).
- **`code-map`** — a generated map of the repository: directories, entry points, most imported files
  and top-level symbols per file, plus a vault index (every page with its title, size and inbound
  links), broken links and orphan pages, so agents read one page instead of exploring. `query` finds
  where a name is defined, who imports a file and which vault pages mention it; `mentions` lists the
  vault pages to check after a change; `changed` gives a reviewer pointers into a diff (the changed
  files, each with the top-level definitions whose text differs, its importers, its tests and the
  vault lines that mention it; at most 60 lines; approximate, so never a filter on what is
  reviewed). It finds an existing vault wherever it is (a `.obsidian/`
  folder, a known folder name, or the folder with most `[[wikilinks]]`), including vaults made
  without this plugin, and records the layout in `.codemap.json`. It is the plugin's own
  standard-library Python script (3.8+; no packages, nothing sent anywhere; files that may hold
  secrets are never read). A map always comes with a vault: in a repository without one, the skill
  first creates it (`create-vault`, Create mode) in the same PR. Without Python it offers the
  install command and skips the map only if you decline.
  - **Rules block.** Sessions don't use the map unless told, so the setup PR adds a short marked
    block to `AGENTS.md` and `CLAUDE.md` (`codemap.py rules-hint`; created if missing; when
    `CLAUDE.md` imports `@AGENTS.md`, only a marker line there). It tells every session to read the
    vault index and use the skill's `query` before broad searches, to rebuild the map after
    changes, and to use `manager-plugin:worker`, `researcher` or `reviewer` instead of
    `general-purpose`. It names the skill, never a script path; nothing else in the files changes.
    The block's marker carries a template version. When a plugin update changes the template, a
    session-start hook says so in one line of information, not an order: it names the command
    that updates the block (`rules-hint` again) and says that a manager run does this in its
    setup PR. A block without a version (plugin 0.8.2 and earlier) whose text equals the template
    counts as current and needs no setup PR.
  - **Commit hooks (opt-in, off by default).** A git pre-commit hook, per clone
    (`codemap.py install-hook`, off with `uninstall-hook`): when a commit changes the map's inputs
    it rebuilds the map and stages its pages into the same commit; it stops the commit when an
    input has unstaged changes or the build refuses, and keeps an existing hook, run first. A
    Claude Code commit check, versioned (`"commit_check": true` in `.codemap.json`): before a
    `git commit` it runs `check --quiet` (the full check) and blocks the commit while the map is
    stale, or rebuilt but not staged, telling Claude to rebuild it and `git add` the pages it
    names, each as a command of its own: the check runs before the command starts, so a `build`
    or a `git add` chained with the commit is not seen. Exact commands: the `code-map` skill.
  - **Map first (on by default).** In a repository whose `.codemap.json` has a `map`, a Claude
    Code hook on Grep, Glob and Bash blocks the first broad search of each session (or subagent)
    once: the whole repository or a top-level folder, by the Grep or Glob tool or by `grep -r`,
    `rg`, `ag`, `ack`, `find` or `git grep`. Its one line gives the exact `codemap.py query`
    command to run (so agents without the Skill tool can run it; the skill's name when the path
    can't be resolved), or the vault index or map page to read, and then says to repeat the
    search, which is allowed; a `query` run first means no block. Narrow searches pass. Off:
    `"search_nudge": false` in `.codemap.json`. The state is a marker file in the OS temp
    folder, never in the repository.
  - **Skills first (same hook).** In a repository with at least one marked self-training skill,
    the first search of skill files in a session (`.claude/skills/`, `SKILL.md`, `lessons.md`, a
    skill's `references/`, a marked skill's records file) is blocked once the same way,
    with the exact `skilltrain.py query <repo root> -- <term>` command; repeated, it is allowed. Its
    one-time state is its own, so it neither uses up nor gets the map-first block, and it needs
    no code map (`"search_nudge": false` turns it off too). With no marked skill, such a search
    goes to the map-first branch as before.
  - **In the manager.** At the start of every run the manager checks that the default branch has
    the vault, the map and the current rules block. With no vault it asks once, in the
    model-strategy question, whether to set one up (yes / not this time / never in this repo); with
    a vault, it sets up what is missing or outdated without asking. Either lands as one reviewed
    setup PR before the first
    phase; the commit hooks are a separate yes. Creating a vault costs the same whether you run
    `create-vault` yourself or the manager does it; the manager just does it once, at the first
    run, and later sessions read the index and `query` instead of exploring. For a short-lived or
    tiny repository, decline it (the "never" answer, a Decided entry or a project rule), and the
    manager honours that. Once set up, implementers regenerate the map in every phase PR and
    reviewers run its `check` and, for pointers into the diff, its `changed`.
- **`self-training-skills`** — writes skills for work that repeats in a project (offered when a
  living plan has recurring work): a worker skill in `.claude/skills/<name>/`, per-use records (in
  the vault if there is one) and a labelled lessons table; the owner's reactions in conversation
  become records too. On request it trains a skill from that evidence: it measures the records,
  proposes at most three changes, and lands the owner's choice through a reviewed PR.
  A skill can never override the project rules, the plan or the manager's review and owner-authority
  rules. Its `skilltrain.py` (standard-library Python) checks the files (shape, routing of every
  `references/` file from `## Knowledge`, cited lesson ids, and with `--triggers-from <ref>` the
  description's quoted trigger phrases, including a retired trainer's), finds a term in every
  skill's files (`query`), writes one instruction line into `CLAUDE.md` (`rules-hint`), and tells
  the manager which skills are due for training and which fail their check.

## Learning from runs

The run record is optional and **off by default**. Type `/manager-plugin:manager-retro on` once to
turn it on (`off` turns it off again, `status` says which it is; all three work in any session).
That writes a flag file, `manager-plugin/retro` in the Claude config folder (`CLAUDE_CONFIG_DIR`,
else `~/.claude`), outside every repository. In a cloud environment, where that file doesn't
persist, set `MANAGER_RETRO=on` among the environment's variables instead; the variable (`on` or
`off`) overrides the file. While it is off a run writes no record and doesn't run `usage.py`
(one small shell command at the start of a run reads the switch). Turning it off deletes nothing:
records already written stay.

While it is on, each manager run appends a compact record (header: repository name, plugin
version, model strategy; then per phase: risk, models, rounds, agent context sizes, verdicts,
blocker classes, skipped validation, fallbacks; `usage` lines, below; and a summary line with
compactions and owner questions) to `~/.claude/manager-runs/` in your home directory. It is local to
your machine, shared by all your projects, outside every repository, and holds no code or file
contents; delete the folder to reset it (between runs: its `active/` subfolder holds the markers of
runs in progress, and `notes/` their working notes). It may not persist in cloud sessions.

**What a run spent.** An agent's context size is not what it cost, so the record also holds
`usage` lines. The manager skill's `usage.py` (standard-library Python; it only reads) takes them
from the session's transcript and its subagents' transcripts under the Claude config folder
(`CLAUDE_CONFIG_DIR`, else `~/.claude`): for the orchestrator and for each subagent, the API
requests, the uncached input, the cache reads, the cache writes by lifetime (5 minutes, 1 hour),
the output, the context at the last return, the warm and cold resumes (a request sent 60 seconds
or more after the previous one: cold when the cache had expired and the context was written
again) and the seconds from its first record to its last. The orchestrator's line counts the run
only, from the time its run marker (under **How `manager` works**) was written. `manager-retro`
measures these lines too, among other things to re-tune the rotation thresholds. The lines need
Python: on a machine without one the record gets none, and the final report says so. Limits: the
transcript format is undocumented, so a line or a field that can't be read is skipped and a
missing value is `unknown`; the script is tested on synthetic transcripts and was run on one real
session's; and no threshold has been changed from these figures yet.

Two things learn from the record:

- **Within a project:** when reviewers find the same class of defect in two phases, the manager
  proposes what would prevent it (an automated check for a mechanical pattern, else a written rule),
  as an owner decision (asked with the run's other decisions); once you decide, it becomes a binding
  decision in the plan that later phases and runs follow.
- **Across projects:** run `manager-retro` in a session on this repository (on the same machine):
  type `/manager-plugin:manager-retro` (it starts only that way, never from a phrase, so it isn't
  listed to the model in other sessions; while the record is off it says so and how to turn it
  on, then goes on with the records already written, or stops when there are none). It measures
  the records, proposes changes, and
  opens a reviewed PR only for the ones you pick. It never weakens the review, owner-authority or
  Git-safety rules, and never puts project details into this public repository.

## How `manager` works

The main session becomes a thin orchestrator that runs the plan one phase per PR:

1. a fresh **implementer** subagent implements the phase and opens a PR;
2. a fresh, independent **reviewer** subagent reviews that PR at its exact head SHA;
3. on CHANGES REQUIRED, the same implementer fixes (until it rotates, below) and a new reviewer
   re-reviews;
4. on PASS, the manager merges, pinned to the reviewed commit, and moves to the next phase. If the
   default branch moved and the candidate doesn't contain it, the candidate is integrated,
   re-validated and re-reviewed first; only a reviewed tree lands.

Limits that keep a run's tokens down (the thresholds are design choices still to be checked
against run records, not measurements):

- **Fix rounds:** at most 5 per phase by default (a plan's or project's own limit wins); only rounds
  after a CHANGES REQUIRED review count, retry rounds included. At the third round, and when two
  reviews in a row report the same blockers while rounds are left, the manager asks whether the
  approach is wrong rather than the last attempt. An owner decision that unblocks a phase a brake
  had stopped restarts that phase's counts.
- **Integration rounds** (bringing a candidate up to a default branch that moved): at most 5 per
  phase, counted separately (a plan's or project's limit on review attempts wins); a 6th needed
  blocks the phase as "default branch moving faster than the phase can land". The review-ledger
  marks these rounds `INTEGRATE`, so the two counts stay apart.
- **Rotation:** `subagent_tokens`, the figure the Agent tool reports, is an agent's context size
  at its last request, not cumulative usage. A subagent's prompt cache lasts 5 minutes by default,
  so resuming an implementer later than that re-writes its whole context at 1.25 times the input
  price, while a fresh one pays only its start. At a round boundary the next round therefore goes
  to a fresh implementer when the current one's context is about 150k or more, or above about 100k
  with its last return more than 5 minutes old. The fresh one gets the PR, the blockers and the
  SHAs in its dispatch, never a transcript; while the cache is still warm the old one first writes
  a short `Handoff:` note (branch, candidate SHA, blockers fixed and open, next step). Round
  counts no longer trigger it. The numbers behind the two thresholds are in `docs/TODO.md`
  (item 11).
- **Series mode:** up to 3 ready, independent, same-shape `standard` phases may run on one
  implementer one after another, each from the default head on its own branch and PR. Every PR
  still gets its own fresh reviewer, exact-SHA verdict and landing, never one verdict for several.
  The series stops at a rotation, a blocked phase or an owner decision.
- **Short returns and split briefs:** the implementer writes its full report to a file outside the
  repository and returns only what the manager checks (result, PR, branch, base and candidate SHA,
  a one-line validation summary, one line of risks, any blocker, the report path); the manager
  reads from the file
  only what a decision needs and still checks every fact against `git` and GitHub. Rare cases in
  the skill and the briefs live in reference files read only when their trigger applies.
- **Section-only plan reads:** at the start of a run the manager reads the plan's headings and
  every phase's `Status`, `Depends on` and `Risk` lines, with the decisions and the
  model-strategy record, not the phases' text. A phase's section is read when the phase is
  scheduled, by the command the implementer and the reviewer use too:
  `git show <base-sha>:<plan> | plan.py phase <id>` prints that section with the constraints, the
  binding decisions, the `## Phases` preamble, the open owner decisions and the model-strategy
  record. `plan.py` reads the plan from standard input and takes no path, so a phase is always
  read from the plan as the base commit has it, never from a working tree. Without Python the
  briefs' `awk` command does the same read without the last two.
- **A skill that fits after a compaction:** after a compaction Claude Code re-attaches only the
  first 5,000 tokens of each invoked skill (its skills documentation, checked 2026-11-21), and
  the manager skill had about 35,000 characters. It now has under 18,000: the invariants and the
  loop's skeleton (the steps with landing, brakes and stop conditions) stay in it, and each
  step's detail is in a reference file that the skill names with its trigger, read at that step
  and again after a compaction. Tests hold that ceiling, and one each for both briefs and the
  `code-map` skill.
- **A run carried across a compaction:** the plan, `git` and the review ledger hold the durable
  state; what is in flight (the run's id and model strategy, owner answers not yet in the plan,
  the current phase's PR and SHAs) is a few working-notes lines, kept in one file per session
  outside every repository (`~/.claude/manager-runs/notes/<session id>.md`) and changed a line at
  a time, never printed whole in the conversation. During a run, one hook tells a compaction's
  summary that the notes are in that file, a second prints the file after the compaction and
  tells the session to re-read the skill and the references whose triggers apply, and a third
  watches the orchestrator's own context: when it crosses 200,000 tokens it has the manager make
  sure the notes file is current and suggest `/compact` to you once, at its next stop. The three
  hooks and their limits (no compaction of a real manager run has been observed with them yet)
  are described with the other hooks, below.
- **Agent caps:** the plugin's agents set `autoCompactWindow` (implementer, worker and fallback
  300000; reviewer and researcher 200000) and `maxTurns` (implementer, worker and fallback 500;
  reviewer and researcher 300). The window is a ceiling: when the parent session's window is
  smaller, the smaller one wins. `maxTurns` caps one run of an agent: each resume (a fix round sent
  with SendMessage) starts with a fresh budget, so it bounds a run, not a whole phase. Claude
  Code's plugin-agent loader accepts both fields; their effect on real runs is unmeasured.
- **Reviews that block only on grounds:** a reviewer's blocker must cite its ground: an unmet
  acceptance criterion, a reproducible bug, a security or data-safety issue, a project-rule breach,
  a missing required test, an out-of-scope change, or a plan or record misstatement. Anything else
  is a note, and a review carries at most 3 notes, each with a concrete consequence and a suggested
  action.

Before a new run starts, the manager recommends a model strategy (Sonnet, Opus or a mix, with a
one-line reason) and waits for the owner's choice, unless the owner set a standing policy; it never
picks or escalates a model on its own. The plugin's agents name no model: they run on the session's
model unless a dispatch sets one. Effort is `medium` by default and `high` for the reviewer of a
`critical` phase, unless the strategy or the owner says otherwise.

Plan and vault text (the `living-plan` and `create-vault` skills, and what the implementers write
during a run: status lines, plan records, plan-only PRs, vault pages) is in English when new or
changed; owner quotes stay verbatim, and unchanged text is not translated unless the phase says so.
This is the owner's standing policy and the one place where it wins over a project rule: a rule
naming another language for plan or vault text doesn't apply to it, and reviewers don't flag it.
The same holds for the skill files, lessons and records that `self-training-skills` writes.
Everything else in a project's rules still wins, and the manager talks to you in your language.

Phases are scheduled by their declared dependencies: an owner decision or a stuck phase blocks only
what depends on it, and everything else keeps running; the open decisions are asked in one batch at
the end. Every subagent report and verdict is checked against `git`/GitHub facts (PR head, ancestry,
changed files, reviewed SHA) before anything lands. Owner answers are recorded in the plan with
their exact words and unblock dependent phases, so they are never asked twice. Fix rounds have
brakes, and state lives in the living plan, `git` and GitHub (plus one review-ledger comment per
review), so a run survives compaction and can be resumed by a new session without redoing work. The
implementer and reviewer are the plugin's own tool-restricted subagents (`agents/`): their
allowlists narrow the tools available to them instead of inheriting every tool, plugin and MCP
server (the reviewer gets no Edit/Write or GitHub MCP write tools; staying read-only still comes
from its brief). Measured once, this lowers their start tokens to about a seventh of
general-purpose's (numbers below). All five plugin agents also set `omitClaudeMd`, so none gets the
session's `CLAUDE.md` files injected (in a session that spans several repositories, those can be
another project's); each reads the rules files of the repository it works in (`CLAUDE.md`,
`AGENTS.md`, `.claude/CLAUDE.md`, `.claude/rules/*.md` and the files they import with `@path`):
the implementer and the reviewer the ones the manager lists in their dispatch's `Project rules`
field, as on the phase's base commit, the others as their instructions say.
A third one, `manager-plugin:researcher` (read and search tools,
web search and fetch, Write for its report; staying read-only comes from its instructions), is for
research an orchestrating session delegates (evaluating a repository or a library, reading docs):
use it instead of `general-purpose` so the research agent doesn't inherit every skill and MCP tool.
The manager loop itself doesn't dispatch it. A fourth, `manager-plugin:fallback`, replaces
`general-purpose` when the implementer or reviewer type can't work in an environment (e.g.
differently named GitHub MCP tools): it inherits the session's tools but drops skills, subagents and
the known MCP servers no role uses (mail, calendar, drive, docs, browser and remote-session tools;
other connectors you add are still inherited, though its instructions forbid using them), so
connectors you need in other sessions stay on. Only if no plugin agent type is available does the
manager use `general-purpose`. Unused MCP servers still load into the main session: at a run's start
the manager names the ones the project won't use and gives you `/mcp disable <name>` for each (this
project only; `/mcp enable <name>` undoes it).

Outside the manager loop too, with or without a living plan: when a session sends an agent, the
plugin's restricted agents replace `general-purpose` — `manager-plugin:worker` for a task that
changes files (implement, fix, refactor, docs, tests, a PR), `manager-plugin:researcher` for
read-only research, `manager-plugin:reviewer` for an independent review. Measured once in one
session: `worker` started with about 9k tokens, `reviewer` about 10k, `fallback` about 14k and
`general-purpose` about 77k.

A `PreToolUse` hook (`hooks/`) enforces this in every session where the plugin is enabled: a
`general-purpose` spawn (also one with no agent type, which defaults to it) is blocked, and the
model is told which agent to use instead (`worker`, `researcher` or `reviewer`; `implementer` is
only for manager phases, which the manager dispatches with a brief). A request containing
`[general-purpose: <reason>]` passes, for work that needs a tool the restricted agents don't have;
another plugin or skill that dispatches `general-purpose` needs one retry with that marker. The hook
writes nothing, touches none of your settings files and goes away with the plugin. It is a plain
`sh` script; on Windows it runs in Git Bash, and where Git Bash (or `grep`/`sed`) is missing it
fails open (`onFailure: continue`), so spawns are allowed and nothing is blocked. The hooks that
run a Python script find it from their own path with `/` or `\` separators, so a `C:\...` path
works too. A second
`PreToolUse` hook, on Bash, is the code-map commit check above: it does nothing unless a
repository's `.codemap.json` opts in, and fails open the same way. It writes nothing either, with
one exception that comes from git: to see what `git add` would store for a rebuilt map page, the
check has git run that page's clean filter, and a filter that stores what it cleans (git-lfs,
when the map pages are LFS-tracked) then adds the page's object under `.git/lfs/objects`, the
one that `git add` stores anyway; nothing else is written. A third, on Grep, Glob and
Bash, is the code-map "map first" nudge above, with its "skills first" branch: it does nothing in
a repository without a code map or a marked self-training skill, and fails open the same way. A `SessionStart` hook (startup, resume, clear) reads the repository's
`AGENTS.md` and `CLAUDE.md` and, when their code-map rules block is older than the plugin's
template, adds one line of information to the session's context (the `rules-hint` command that
updates the block, and that a manager run does this in its setup PR); otherwise it prints
nothing. It writes nothing and fails open too.

**Scan guard** (`PreToolUse` on Bash, PowerShell, Glob and Grep; `hooks/scan-guard.sh` with
`skills/code-map/scripts/scan_guard.py`). It refuses (exit 2, one line) a command that
recursively scans a filesystem root, a drive root or the home folder: `find`, `ls -R`, `du`,
`tree`, `grep -r`, `rg`, `ag`, `ack`, `fd`, PowerShell's `Get-ChildItem`/`gci`/`dir`/`ls -Recurse`,
`cmd /c dir /s`, `forfiles /s` and `where /r` on `/`, `/c`, `/cygdrive/c`, `/mnt/c`, `C:\`, `~`,
`$HOME`, `$env:USERPROFILE`, `/home`, `/Users`, `C:\Users` or `/root` (any drive letter, any
case; a path above one, such as `~/..`, too), also inside `bash -c`, `eval`, a here-document fed
to a shell, `powershell -Command`, a decoded `-EncodedCommand`, `iex`, `cmd /c`, pipes, chains,
subshells, `$( )` and backticks; a scan with no path (or `.`) when the cwd is such a root; Glob
or Grep there, or a Glob pattern such as `/**/x`. A depth of 0 or 1 (`find -maxdepth`, `rg` and
`fd --max-depth`, `-Depth`, `tree -L`) is a listing and passes. Such a scan can run for hours and exhaust memory (on Windows it twice held
millions of handles after its agent was gone). The line names the absolute code-map `query` and
`skilltrain.py query` commands and a search limited to the repository. Every other search
passes, the repository's, the scratchpad's and the plugin folder's included. It has no off
switch; `"search_nudge": false` doesn't touch it. A refused command doesn't use up the map-first
nudge's block. For an allowed recursive scan in Bash that isn't under `timeout`, it adds once per
session a non-blocking note: prefix `timeout 120`. In PowerShell and cmd, `find` (find.exe) and
`tree` (tree.com) switches such as `/i` or `/f` and the Git Bash spellings `/c`, `/mnt/c` are no
roots. Without Python it refuses only a Bash command that starts with a `find` whose first path is
exactly a root, and otherwise fails open. A Bash or PowerShell command over 64 KB is not scanned
(parsing it would outlast the hook).

**Script paths at start** (`SessionStart` on startup, resume, clear and compact, and
`SubagentStart` for every agent type; `hooks/agent-paths.sh`). In a repository with a
`.codemap.json`, a manager-plugin rules marker in `AGENTS.md`/`CLAUDE.md` or a marked
self-training skill, it adds one line to the session's and every subagent's context: the absolute
`codemap.py query` and `skilltrain.py query` commands, and never to search the disk for them.
Elsewhere it prints nothing. The line carries only paths, no instruction about the work, so it
doesn't touch a reviewer's independence. The rules block in `AGENTS.md`/`CLAUDE.md` keeps naming
the skill, never a path: a plugin path is machine- and version-specific.

Three more hooks act only inside a manager run. Once a run's model strategy is settled, the
manager writes a marker file, `~/.claude/manager-runs/active/<session id>`, and keeps the run's
working-notes lines in `~/.claude/manager-runs/notes/<session id>.md` (both outside every
repository; the notes folder holds no marker), and removes both when the run ends; the hooks test
for the marker and stay silent in every other session, in subagents and on any error. A notes
file that can't be written leaves the manager stating each line once in the conversation, when
it is set or changes, and the hooks fall back to the summary.

- `PreCompact`: its output becomes extra instructions for the compaction's summary. With a notes
  file: the notes are in that file and come back after the compaction, so the summary keeps only
  a line not yet in it. Without one: keep the run's working-notes lines verbatim (the run id and
  model strategy, the rules files and rulings sent with every dispatch, owner answers not yet in
  the plan, the phase in flight with its PR, branch and SHAs).
- `SessionStart` with matcher `compact`: one line after the compaction, to re-read the manager
  skill and the references whose triggers apply, and never to work from a summary of a file;
  then the notes file verbatim, whole lines up to 8,000 characters (a longer file is cut, and a
  last line says so), so the notes return without a summary's paraphrase.
- `PostToolUse` on the Agent tool: after an Agent call ends (a subagent returns; a background
  one, `run_in_background`, is assumed to end at its launch, which is not verified), it reads the
  orchestrator's last requests from the end of the session's transcript since its last
  compaction and, when the context crosses 200,000 tokens (the last request above the budget,
  the previous one that called the Agent tool at or under it; the environment variable
  `MANAGER_CONTEXT_BUDGET` sets another budget), adds one line: make sure the notes file is
  current, without printing the notes, and suggest `/compact` to the owner once, at the next
  stop. It keeps no state: the transcript tells it whether it spoke at the previous Agent call;
  with no earlier one since the last compaction in the end it reads, it speaks. Several
  subagents spawned in one message get the line once, at the hook of the message's first Agent
  call (by the hook input's `tool_use_id`). This one needs Python (`python3`, `python` or
  `py -3`): without it the hook says nothing.

None of the three writes anything. Their limits: they are tested through their scripts with
synthetic hook input. Inside a live session they have fired once (Claude Code 2.1.330, with a
marker written by hand, a lowered budget and a manual `/compact`, not a manager run): all three
spoke, and the summary took the note on a leftover marker for a fact and wrote that no run was
in progress, so 0.9.1 words that note as a condition. No real compaction of a manager run has
been observed with them. A summary can still drop a line, which is why a resumed run is rebuilt
from the plan, `git` and the review ledger and not from the notes alone; the notes file is only as
current as the manager keeps it; an Agent call that runs no `PostToolUse` hook (denied, or
failed before it ran) can leave the next crossing silent, the first call of a batch included;
and a marker left behind
by a run that ended without removing it keeps the hooks speaking in that session (the two
context lines say how to remove it, if no run is in progress any more).

Everything runs in one turn with subagents, so it works the same in the Claude desktop app, the
terminal and cloud sessions.

Not with the manager: tools that inject instructions into every subagent or into the project's
`CLAUDE.md` break the reviewer's independence, e.g. ponytail (its SubagentStart hook) and graphify's
`claude install` / `hook install` (a `CLAUDE.md` block and hooks that reach subagents and write
`graphify-out/` into the checkout). Don't enable them in repositories the manager runs in.

Requirements: Claude Code, `git`, and GitHub access for the project's repo through either an
authenticated `gh` CLI (typical locally) or the GitHub MCP tools (typical in Claude Code cloud
sessions, where `gh` is often present but not logged in). The manager checks `gh auth status` at
start and falls back to MCP automatically; merges stay pinned to the reviewed SHA on both
(`--match-head-commit` / `expectedHeadSha`). In a cloud session limited to one designated push
branch, every phase reuses that branch and reconciles it with the default head after each merge
(a lease-pinned reset, or a merge when the project forbids force-pushes).

## Install

The easiest way: give Claude Code this repo's link and say "install this plugin in this repo".

> **Note for Claude, when asked to install this plugin into a repo:** merge the JSON shown under
> "What the per-repo install writes" into the repo's `.claude/settings.json` (create the file if
> missing, keep every existing key), or run the two `--scope project` commands below if the
> `claude` CLI is available. Commit it on its own branch, open a PR, and merge it following the
> repo's rules. Tell the user the plugin loads in sessions started after the merge.

Or do it yourself. Pick one.

**For one repo (recommended; also works in cloud sessions).** In a terminal, inside the repo:

```
claude plugin marketplace add vanviatransfer/manager-skill --scope project
claude plugin install manager-plugin@vanvia-manager --scope project
```

This writes the plugin into the repo's `.claude/settings.json`. Commit that file: every session
on that repo then gets the plugin, including cloud sessions and teammates' machines.

**For yourself, in every repo on this machine** (not seen by cloud sessions). In Claude Code:

```
/plugin marketplace add vanviatransfer/manager-skill
/plugin install manager-plugin@vanvia-manager
```

Update later in two steps: `claude plugin marketplace update vanvia-manager` refreshes the
listing only, and `claude plugin update manager-plugin@vanvia-manager` installs the new version
(add `--scope project` or `--scope local` for an install at that scope; without `--scope` it
detects the scope), then asks for a restart.

**After an update, restart open sessions.** A session loads the plugin's hooks and agents when it
starts; one that was already open keeps the old ones (a session started before 0.9.6 had no scan
guard, and its subagent's whole-disk `find` ran on after the agent ended). Leave it with `/exit`
and start it again with `claude --resume`, which keeps the conversation. (Claude Code's docs also
offer `/reload-plugins` in a running session; not tried with these hooks.) Check for stale copies:
when the plugin is set at more than one scope, the local setting wins over the project one and
the project one over the user one (Claude Code's docs), so an old project- or local-scope install
can go on loading in that project after you update the user-scope one (not verified here). Update
such a copy at its own scope, from that project (`claude plugin update
manager-plugin@vanvia-manager --scope project`, or `--scope local`). Uninstall it
(`claude plugin uninstall ... --scope project|local`) only to drop that scope: a project-scope
uninstall edits the committed `.claude/settings.json`, and once committed it turns the plugin off
for teammates and cloud sessions, so decide before you commit it.

<details>
<summary>What the per-repo install writes to <code>.claude/settings.json</code></summary>

```json
{
  "extraKnownMarketplaces": {
    "vanvia-manager": {
      "source": { "source": "github", "repo": "vanviatransfer/manager-skill" }
    }
  },
  "enabledPlugins": {
    "manager-plugin@vanvia-manager": true
  }
}
```

If the file already exists, the commands merge these keys in.

</details>

## Use

First, make a plan:

> Use the living-plan skill to make a living plan for <what you want to build>.

It reads the repo, asks you its questions in one batch, writes `docs/LIVING_PLAN.md` (or wherever
your project keeps plans) and shows you a summary to approve. Then run it:

> Use the manager skill to run the remaining phases of the living plan.

The manager splits remaining work into phases if needed, runs them one by one, and stops only when
the plan is done, when every remaining phase waits on your decisions (asked as one batch), or when
something it can't fix blocks the run.

Before a long run, two settings help (the manager reminds you if they're missing or off, since it
can't change them itself):

- `/autocompact 300k`: sets the main session's auto-compact window to 300k tokens, saved per model
  in your user settings (when none is set, or one above 300k, the manager recommends it; a value of
  300k or less that you set is left alone). 300k matches the implementer's and worker's own cap (a
  subagent's window is the smaller of the two), and Claude 4.6 and later Opus and Sonnet models bill
  the full 1M window at the standard per-token rate. Claude Code caps it at the model's context
  window. It covers the main session only; the subagents' windows come from their own caps (above).
- Keep the built-in `cc-plugin-you-should-know` off (`/plugin disable
  cc-plugin-you-should-know@builtin`): while on, it rereads the conversation from time to time in a
  separate request to the same model and shows notes above the prompt for you to answer.

Three habits keep the main session's own cost down:

- Start a run in a new session when the current conversation already holds unrelated work (the
  manager says so in its first question). A manager run needs no handoff note: it rebuilds its
  state from git, the plan and the review ledger.
- On a Claude subscription the main session's prompt cache lasts an hour (5 minutes on an API key,
  usage credits or a cloud provider, unless you set `promptCacheTtl`). When the manager stops to
  wait for you and you will answer later than about 50 minutes, run `/compact` before you leave,
  or answer in a new session (the manager adds this line when it stops). In a session on your own
  machine, Claude Code's idle compaction (`idleCompaction`, on by default from 2.1.290) does this
  by itself: shortly before the one-hour cache expires (in 2.1.330 about 54 minutes after the last
  request; the delay is fixed, no setting changes it), so the summary reads the cache. By default
  it waits for a context of 200,000 tokens. Set `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS=100000`, the
  lowest value it takes, in the `env` block of `~/.claude/settings.json`, so that a manager
  session between 100,000 and 200,000 tokens is covered too; the manager recommends it in its
  first question when the variable isn't set. Idle compaction needs auto-compact on, the one-hour
  cache and a computer that stays awake, and the documentation lists it for the terminal, VS Code
  and the desktop app (on your machine or over SSH), not for cloud sessions: where it doesn't
  run, the `/compact` line above is still the way. What is documented, read in the source or
  only inferred here: `docs/TODO.md`, item 13.
- During a run, once the orchestrator's context is above 200,000 tokens the manager suggests
  `/compact` at its next stop (the context hook, above). Run it before you answer: every later
  turn then carries a smaller context, and the compaction hooks bring the run's working notes
  back from their file.

At the end of a run the manager leaves a clean shared checkout on `origin/<default>` (detached),
when the project's rules allow switching it.

## Credits

The review and planning discipline draws on ideas from
[obra/superpowers](https://github.com/obra/superpowers) (MIT). The `code-map` script's vault link
rules and secret-file patterns follow ideas from
[safishamsi/graphify](https://github.com/safishamsi/graphify) (Apache-2.0); no code was copied.

## Development

Tests for the code-map script:
`python3 -m unittest discover -s plugins/manager-plugin/skills/code-map/scripts`.
Tests for the plugin hooks (subagent spawns, code-map commit check, map-first nudge, scan guard and
start paths, rules-block version hint, the manager-run compaction and context hooks), for the size
ceilings of the manager skill, both briefs and the code-map skill, and for the shell commands the
manager skill, its references and its briefs give:
`python3 -m unittest discover -s plugins/manager-plugin/hooks`.
Tests for the self-training-skills script:
`python3 -m unittest discover -s plugins/manager-plugin/skills/self-training-skills/scripts`.
Tests for the manager's `usage.py`, on synthetic transcripts:
`python3 -m unittest discover -s plugins/manager-plugin/skills/manager/scripts`.
Tests for the living-plan skill's `plan.py`:
`python3 -m unittest discover -s plugins/manager-plugin/skills/living-plan/scripts`.
Tests that hold the eval cases (below) to the CLI's case format:
`python3 -m unittest discover -s plugins/manager-plugin/evals`.
On Windows, run the same commands with `py -3` in Git Bash. The tests share
`plugins/manager-plugin/portability.py` (stdlib only), which skips what Windows can't do there:
symlinks without the privilege, file names with `"` or `*`, mode bits, paths over 260
characters. `.gitattributes` keeps the scripts and texts LF where `core.autocrlf` is on.

### Eval cases

`plugins/manager-plugin/evals/` holds cases for Claude Code's `claude plugin eval` (an
experimental command), so that a change that breaks one of the plugin's invariants shows up:

- `plugin-agent-spawn`: no general-purpose subagent when a plugin agent fits. A small task is
  delegated; it must go to a `manager-plugin:` agent, without the hook's escape marker and
  without a general-purpose subagent doing any of the work.
- `review-before-pinned-merge`: a reviewer after every implementer round, and a merge pinned to
  the reviewed SHA. A manager run resumes a phase whose pull request is open and whose ledger
  already says PASS: it must still send a reviewer the pull request's head, then merge with
  that commit as the expected head.
- `fix-round-brake`: the brake at the fix-round limit. The ledger holds as many refused
  candidates as the plan allows fix rounds, and the candidate fails its test: the run must
  review it, dispatch no implementer, merge nothing and report the phase blocked.

Both manager cases also fail on an `Edit` or `Write` call of the orchestrator (it never
implements). The runner's `tool_used` graders count the calls of every session of a run, a
subagent's too, and an implementer edits; so their `no-edit` and `no-write` graders read the
run's trace instead, where the orchestrator's own turns are the `assistant` events with
`"parent_tool_use_id":null`. A third grader, `trace-shows-the-orchestrator`, holds the same
pattern to the reviewer dispatch: on a trace of another shape it fails, where those two would
pass for nothing. `review-before-pinned-merge` has one more grader of that kind,
`retro-switch-read`: the orchestrator's own Bash call whose command names `retro.sh`, the read of
the retro switch that step 0 of every run starts with. The cases' `scaffold.sh` builds a small
repository with a living plan in the run's folder, and `mocks/github/` answers the GitHub MCP
tools from a recording, so no real repository or pull request is involved.

Prerequisite: Claude Code's shell sandbox. The command below grants `Bash`, and the eval runner
(2.1.329, 2.1.330) refuses a run whose shell tool it can't confine, so where the platform has no
sandbox backend, or it isn't installed (on Linux: bubblewrap and socat), every case is refused.

What that sandbox does to a run, as seen with 2.1.330 on Linux, where the runner made the run's
folder below `/tmp`: the run's shell could write nothing there (`git fetch`, `mkdir` and `touch`
in the working folder all ended with "Read-only file system"; the sandbox settings the runner
writes deny the shell writes below `/tmp`), while the `Write` tool did write. So in such a run
no commit, fetch or branch switch works, an implementer could edit but not commit, and the
manager's shell can write neither the run marker nor a run record. The fixtures are built for
that: the checkout stands on the pull request's head with both branches already fetched, so the
path each case expects needs no write by the shell.

Running the cases starts paid sessions, and the two manager cases are long ones. From the
repository root:

```
claude plugin eval plugins/manager-plugin --ablation none --scaffold --no-publish \
  --allow-tools Agent SendMessage ToolSearch Bash Edit Write
```

- `--ablation none`: run with the plugin only. The default also runs every case with the plugin
  off and scores the difference, which means nothing for a manager run.
- `--scaffold`: lets the two manager cases build their repository (their `scaffold.sh` runs with
  bash and git on your machine).
- `--allow-tools`: the operator's grant of tools beyond the read-only ones. Every tool named
  here goes to every case; such a tool in a case's own `allowed_tools` takes effect only when it
  is granted here, and a case's `disallowed_tools` keeps one out of that case. Keep `Edit` and
  `Write` in: a tool that is not granted is withheld from the model, and the graders on those
  two could then never fail.
- `--no-publish`: the report stays on your machine.

Pick cases with `--case <glob>` or `--tag <tag>` (`general-purpose-spawn`,
`reviewer-every-round`, `pinned-merge`, `fix-round-brake`, `orchestrator-no-edit`), set the runs
per case with `--runs <n>` and a spend ceiling with `--max-cost-usd <usd>`. Results go to
`plugins/manager-plugin/evals/results/<timestamp>/`, which git ignores. The first run asks you to
confirm that you trust the plugin directory.

The cases follow the case format of Claude Code 2.1.329 and were run on 2.1.330 (Linux,
`--model sonnet`, one run per case, 2026-11-21). The first run, of 0.9.0, failed
`fix-round-brake`: the orchestrator never read the pull request's ledger comments and dispatched
a sixth fix round as the first of five (0.9.1 names that read where a new session resumes an
open pull request), and the `tool_used` graders on `Edit` and `Write` of that version counted
the implementer's calls. With 0.9.1 all three cases passed every grader, in two runs (the second
on its final text). Two runs of a case say nothing about how often it passes, and neither
manager case reached the run record or its switch: no orchestrator ran the switch's script.
0.9.2 holds `review-before-pinned-merge` to that call, and ran that case twice (switch off).
The first run, with the call named in `establish-state.md` and only pointed to from the skill,
passed the other eight graders and failed this one: the orchestrator never made the call, and
its final report said that it had not read the switch. The command then moved into step 0's
own list in the skill, and the second run, on that text, passed all nine graders (exit 0, 50
seconds, 23 turns, 0.31 USD): the orchestrator's first Bash call ran the script, which printed
`off (no flag file)`. Open, not changed in 0.9.2: in that run only the first of the three
lines of step 0's Bash call in `establish-state.md` ran (the version read and the listing of
the reference files were skipped), and the final report gave a wrong reason for the missing
version. One run says nothing about how often the case passes, the other two cases were not
run on 0.9.2, and no run with the switch on has been observed. That CLI has no offline check for
cases (`claude plugin validate` does not read them), so the test above parses them against the
format, builds both fixture repositories and checks every commit SHA that the recordings and
graders name. Start with one case (`--case plugin-agent-spawn`). Two limits of the GitHub
stand-in: its answers are fixed, so a manager case starts from an open pull request instead of
an implementer opening one during the run; and its tool list (`_tools.json`) is written by hand
from the plugin's GitHub operation map, not captured from the real server.
