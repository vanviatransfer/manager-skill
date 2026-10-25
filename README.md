# manager-skill

A Claude Code plugin with two skills:

- **`living-plan`** — writes a project's living plan: goal, scope, binding decisions, phases sized
  for one PR each (with acceptance criteria and validation), and open owner decisions.
- **`manager`** — runs that plan to completion.

## How `manager` works

The main session becomes a thin orchestrator that runs the plan one phase per PR:

1. a fresh **implementer** subagent implements the phase and opens a PR;
2. a fresh, independent **reviewer** subagent reviews that PR at its exact head SHA;
3. on CHANGES REQUIRED, the same implementer fixes and a new reviewer re-reviews;
4. on PASS, the manager merges, pinned to the reviewed commit, and moves to the next phase. If the
   default branch moved and the candidate doesn't contain it, the candidate is integrated,
   re-validated and re-reviewed first; only a reviewed tree lands.

Before a new run starts, the manager recommends a model strategy (Sonnet, Opus or a mix, with a
one-line reason) and waits for the owner's choice; it never picks or escalates a model on its own.

Phases are scheduled by their declared dependencies: an owner decision or a stuck phase blocks only
what depends on it, and everything else keeps running; the open decisions are asked in one batch at
the end. Every subagent report and verdict is checked against `git`/GitHub facts (PR head, ancestry,
changed files, reviewed SHA) before anything lands. Owner answers are recorded in the plan with
their exact words and unblock dependent phases, so they are never asked twice. Fix rounds have
brakes, and state lives in the living plan, `git` and
GitHub (plus one review-ledger comment per review), so a run survives compaction and can be resumed
by a new session without redoing work.
Everything runs in one turn with subagents, so it works the same in the Claude desktop app, the
terminal and cloud sessions.

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

## Credits

The review and planning discipline draws on ideas from
[obra/superpowers](https://github.com/obra/superpowers) (MIT).
