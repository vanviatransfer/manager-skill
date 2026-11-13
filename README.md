# manager-skill

A Claude Code plugin with five skills:

- **`living-plan`** — writes a project's living plan: goal, scope, binding decisions, phases sized
  for one PR each (with acceptance criteria and validation), and open owner decisions.
- **`manager`** — runs that plan to completion.
- **`create-vault`** — creates, adopts or refreshes a project vault in `docs/vault/`: short linked
  pages of durable facts about the code (index, glossary, decision records, topic pages), each with
  its sources and a `Verified` line, landed through a reviewed PR. The plan's phases point to the
  pages they need, and the manager's implementers keep those pages current in their phase PRs.
- **`code-map`** — a generated map of the code (`docs/vault/map.md`: directories, entry points, most
  imported files, top-level symbols per file; per-directory pages in large repos) and a `query`
  for where a name is defined and who imports a file, from the plugin's own standard-library
  Python script (3.8+; nothing to install, nothing sent anywhere). When a project has the map, the
  manager's implementers regenerate it in every phase PR and reviewers run its `check`. Without
  Python it is skipped.
- **`manager-retro`** — improves the manager from evidence: reads the compact run records the
  manager keeps on your machine and proposes up to three small changes, landed through an
  independently reviewed PR you choose.

## Learning from runs

Each manager run appends a compact record (header: repository name, plugin version, model strategy;
then per phase: risk, models, rounds, tokens, verdicts, blocker classes, skipped validation,
fallbacks; and a summary line with compactions, owner questions and usage change) to
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
3. on CHANGES REQUIRED, the same implementer fixes and a new reviewer re-reviews;
4. on PASS, the manager merges, pinned to the reviewed commit, and moves to the next phase. If the
   default branch moved and the candidate doesn't contain it, the candidate is integrated,
   re-validated and re-reviewed first; only a reviewed tree lands.

Before a new run starts, the manager recommends a model strategy (Sonnet, Opus or a mix, with a
one-line reason) and waits for the owner's choice, unless the owner set a standing policy; it never
picks or escalates a model on its own.

Phases are scheduled by their declared dependencies: an owner decision or a stuck phase blocks only
what depends on it, and everything else keeps running; the open decisions are asked in one batch at
the end. Every subagent report and verdict is checked against `git`/GitHub facts (PR head, ancestry,
changed files, reviewed SHA) before anything lands. Owner answers are recorded in the plan with
their exact words and unblock dependent phases, so they are never asked twice. Fix rounds have
brakes, and state lives in the living plan, `git` and
GitHub (plus one review-ledger comment per review), so a run survives compaction and can be resumed
by a new session without redoing work.
The implementer and reviewer are the plugin's own tool-restricted subagents (`agents/`): their
allowlists narrow the tools available to them instead of inheriting every tool, plugin and MCP
server (the reviewer gets no Edit/Write or GitHub MCP write tools; staying read-only still comes
from its brief). Whether this lowers startup tokens is to be measured, not assumed.
A third one, `manager-plugin:researcher` (read and search tools, web search and fetch, Write for
its report; staying read-only comes from its instructions), is for research an orchestrating
session delegates (evaluating a repository or a library, reading docs): use it instead of
`general-purpose` so the research agent doesn't inherit every skill and MCP tool. The manager loop
itself doesn't dispatch it.
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

Before a long run, two settings help (the manager reminds you if they're missing, since it can't
change them itself):

- `/autocompact 600k`: sets the main session's auto-compact window to 600k tokens, saved per model
  in your user settings. Claude Code caps it at the model's context window; on a large-window model
  it can make compaction happen earlier than the model's default window, if that is larger.
- Keep the built-in `cc-plugin-you-should-know` off (`/plugin disable
  cc-plugin-you-should-know@builtin`): while on, it rereads the conversation from time to time in a
  separate request to the same model and shows notes above the prompt for you to answer.

## Credits

The review and planning discipline draws on ideas from
[obra/superpowers](https://github.com/obra/superpowers) (MIT).

## Development

Tests for the code-map script: `python3 -m unittest discover -s plugins/manager-plugin/skills/code-map/scripts`.
