# manager-skill

A Claude Code plugin that turns a session into a **manager** for a project's living plan.

The main session becomes a thin orchestrator that runs the plan one phase per PR:

1. a fresh **implementer** subagent implements the phase and opens a PR;
2. a fresh, independent **reviewer** subagent reviews that PR at its exact head SHA;
3. on CHANGES REQUIRED, the same implementer fixes and a new reviewer re-reviews;
4. on PASS, the manager merges, pinned to the reviewed commit, and moves to the next phase.

Fix rounds have brakes, owner decisions are collected and asked in one batch, and state lives in
the living plan, `git` and `gh`, so a run survives compaction and can be resumed by a new session.
Everything runs in one turn with subagents, so it works the same in the Claude desktop app, the
terminal and cloud sessions.

Requirements: Claude Code, `git`, and an authenticated `gh` CLI for the project's GitHub repo.

## Install for yourself

In Claude Code:

```
/plugin marketplace add vanviatransfer/manager-skill
/plugin install manager-plugin@vanvia-manager
```

## Enable for a project (also loads in cloud sessions)

Add to the project's `.claude/settings.json`:

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

## Use

Have a living plan in the repo (a markdown file with the goal, phases or remaining work, and open
decisions), then ask:

> Use the manager skill to run the remaining phases of the living plan.

The manager splits remaining work into phases if needed, runs them one by one, and stops only when
the plan is done, when every remaining phase waits on your decisions (asked as one batch), or when
something it can't fix blocks the run.
