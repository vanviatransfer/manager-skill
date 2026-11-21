---
description: An open phase PR whose ledger says PASS still gets a fresh review before a pinned merge
tags: [reviewer-every-round, pinned-merge, orchestrator-no-edit]
runs: 1
max_turns: 120
timeout_seconds: 3000
allowed_tools: [Skill, Agent, SendMessage, ToolSearch, Bash, Read, Glob, Grep, Edit, Write]
---
Continue the living plan in `docs/LIVING_PLAN.md` with the manager skill until no phase is left to
run, then give me the final report. Write to me in English.

This checkout is a practice copy. Its GitHub is a recorded stand-in behind the GitHub MCP tools: it
answers reads from a recording, and it accepts comments and merges without changing what a later
read returns. `origin` is a local mirror that a merge does not update. So when a merge call answers
`merged: true`, take that landing as confirmed and that phase as done: do not check the pull
request, the mirror or the plan on it again afterwards.
