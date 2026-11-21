# manager-skill

A Claude Code plugin with six skills:

- **`living-plan`** — writes a project's living plan: goal, scope, binding decisions, phases sized
  for one PR each (with acceptance criteria and validation), and open owner decisions.
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
  vault pages to check after a change. It finds an existing vault wherever it is (a `.obsidian/`
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
    session-start hook says so in one line with the command to run (`rules-hint` again, then
    commit); the manager updates an outdated block in its setup PR.
  - **Commit hooks (opt-in, off by default).** A git pre-commit hook, per clone
    (`codemap.py install-hook`, off with `uninstall-hook`): when a commit changes the map's inputs
    it rebuilds the map and stages its pages into the same commit; it stops the commit when an
    input has unstaged changes or the build refuses, and keeps an existing hook, run first. A
    Claude Code commit check, versioned (`"commit_check": true` in `.codemap.json`): before a
    `git commit` it runs `check --quiet` (the full check) and blocks the commit while the map is
    stale, telling Claude to rebuild and stage it. Exact commands: the `code-map` skill.
  - **Map first (on by default).** In a repository whose `.codemap.json` has a `map`, a Claude
    Code hook on Grep, Glob and Bash blocks the first broad search of each session (or subagent)
    once: the whole repository or a top-level folder, by the Grep or Glob tool or by `grep -r`,
    `rg`, `ag`, `ack`, `find` or `git grep`. Its one line gives the exact `codemap.py query`
    command to run (so agents without the Skill tool can run it; the skill's name when the path
    can't be resolved), or the vault index or map page to read, and then says to repeat the
    search, which is allowed; a `query` run first means no block. Narrow searches pass. Off:
    `"search_nudge": false` in `.codemap.json`. The state is a marker file in the OS temp
    folder, never in the repository.
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
    reviewers run its `check`.
- **`self-training-skills`** — writes skills for work that repeats in a project (offered when a
  living plan has recurring work): a worker skill in `.claude/skills/<name>/`, per-use records (in
  the vault if there is one) and a labelled lessons table, plus an optional trainer skill for work
  the owner judges in conversation. On request it trains a skill from that evidence: it measures
  the records, proposes at most three changes, and lands the owner's choice through a reviewed PR.
  A skill can never override the project rules, the plan or the manager's review and owner-authority
  rules. Its `skilltrain.py` (standard-library Python) checks the files and tells the manager which
  skills are due for training.

## Learning from runs

Each manager run appends a compact record (header: repository name, plugin version, model strategy;
then per phase: risk, models, rounds, agent context sizes, verdicts, blocker classes, skipped
validation, fallbacks; and a summary line with compactions and owner questions) to
`~/.claude/manager-runs/` in your home directory. It is local to your machine, shared by all your
projects, outside every repository, and holds no code or file contents; delete the folder to reset
it. It may not persist in cloud sessions. Two things learn from it:

- **Within a project:** when reviewers find the same class of defect in two phases, the manager
  proposes what would prevent it (an automated check for a mechanical pattern, else a written rule),
  as an owner decision (asked with the run's other decisions); once you decide, it becomes a binding
  decision in the plan that later phases and runs follow.
- **Across projects:** run `manager-retro` in a session on this repository (on the same machine):
  type `/manager-plugin:manager-retro` (it starts only that way, never from a phrase, so it isn't
  listed to the model in other sessions). It measures the records, proposes changes, and
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
another project's); each reads the `CLAUDE.md` and `AGENTS.md` of the repository it works in, as
its brief or instructions say. A third one, `manager-plugin:researcher` (read and search tools,
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
fails open (`onFailure: continue`), so spawns are allowed and nothing is blocked. A second
`PreToolUse` hook, on Bash, is the code-map commit check above: it does nothing unless a
repository's `.codemap.json` opts in, and fails open the same way. A third, on Grep, Glob and
Bash, is the code-map "map first" nudge above: it does nothing in a repository without a code map,
and fails open the same way. A `SessionStart` hook (startup, resume, clear) reads the repository's
`AGENTS.md` and `CLAUDE.md` and, when their code-map rules block is older than the plugin's
template, adds one line with the `rules-hint` command to the session's context; otherwise it
prints nothing. It writes nothing and fails open too.

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

Update later with `claude plugin marketplace update vanvia-manager`.

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

Two habits keep the main session's own cost down:

- Start a run in a new session when the current conversation already holds unrelated work (the
  manager says so in its first question). A manager run needs no handoff note: it rebuilds its
  state from git, the plan and the review ledger.
- On a Claude subscription the main session's prompt cache lasts an hour (5 minutes on an API key,
  usage credits or a cloud provider, unless you set `promptCacheTtl`). When the manager stops to
  wait for you and you will answer later than about 50 minutes, run `/compact` before you leave,
  or answer in a new session (the manager adds this line when it stops). Claude Code's idle
  compaction (`idleCompaction`, on by default from 2.1.290) does this by itself in local
  interactive sessions once the context is 200,000 tokens or more; it doesn't run in cloud
  sessions or on smaller contexts.

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
Tests for the plugin hooks (subagent spawns, code-map commit check, map-first nudge, rules-block
version hint) and for the shell commands the manager skill and its briefs give:
`python3 -m unittest discover -s plugins/manager-plugin/hooks`.
Tests for the self-training-skills script:
`python3 -m unittest discover -s plugins/manager-plugin/skills/self-training-skills/scripts`.
Tests that hold the eval cases (below) to the CLI's case format:
`python3 -m unittest discover -s plugins/manager-plugin/evals`.

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

Both manager cases also fail on any `Edit` or `Write` call (the orchestrator never implements):
the one subagent they need is the reviewer, which has neither tool. Their `scaffold.sh` builds a
small repository with a living plan in the run's folder, and `mocks/github/` answers the GitHub
MCP tools from a recording, so no real repository or pull request is involved.

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

The cases follow the case format of Claude Code 2.1.329 and have not been run yet. That CLI has
no offline check for cases (`claude plugin validate` does not read them), so the test above
parses them against the format, builds both fixture repositories and checks every commit SHA
that the recordings and graders name. Expect a first run to need adjusting, and start with one
case (`--case plugin-agent-spawn`). Two limits of the GitHub stand-in: its answers are fixed, so
a manager case starts from an open pull request instead of an implementer opening one during the
run; and its tool list (`_tools.json`) is written by hand from the plugin's GitHub operation map,
not captured from the real server.
