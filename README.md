# claude-plugins

Personal Claude Code plugins.

## living-plan

Skill `orchestrate-living-plan`: the main session becomes a thin orchestrator that runs a project's
living plan one phase per PR. Each phase gets a fresh implementer subagent; each candidate SHA gets
a fresh, independent reviewer subagent; fixes loop through the same implementer with brakes; owner
decisions are collected and asked in one batch. Everything stays in one turn, so it works the same
in the desktop app, the terminal and cloud sessions.

### Enable in a project (local and cloud sessions)

Add to the project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "vanvia-plugins": {
      "source": { "source": "github", "repo": "vanviatransfer/claude-plugins" }
    }
  },
  "enabledPlugins": {
    "living-plan@vanvia-plugins": true
  }
}
```

Then ask: "Use orchestrate-living-plan to run the remaining phases of the living plan."

### Install for yourself on one machine

```
/plugin marketplace add vanviatransfer/claude-plugins
/plugin install living-plan@vanvia-plugins
```
