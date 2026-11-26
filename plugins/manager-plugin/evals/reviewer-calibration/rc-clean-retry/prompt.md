---
description: Reviewer calibration case for retry, phase P1 (Retry decision)
tags: [reviewer-calibration]
runs: 1
model: sonnet
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Agent, Bash, Read, Glob, Grep, ToolSearch]
---
Have the plugin's reviewer review pull request #1 of this practice repository, then give me its
answer.

1. The manager-plugin start line in your context names the absolute path of the plugin's
   `codemap.py`: `<plugin root>/skills/code-map/scripts/codemap.py`. The reviewer brief is
   `<plugin root>/skills/manager/references/reviewer-brief.md`; check that the file exists. Take
   this repository's absolute path from `pwd`.
2. Send one `manager-plugin:reviewer` agent, in the foreground, exactly this message with the two
   paths filled in, nothing else:

   ```
   Read and follow <the reviewer brief's absolute path>.
   Project: <this repository's absolute path> (shared checkout), default branch main
   PR: #1, head branch phase/P1
   Base SHA: 1e20f79431e330bb0853f8d5d24c0eaef1688795   Candidate SHA: 37b3501e78c7ac569b9cc8da6c69fac22d485fd5
   Living plan: docs/LIVING_PLAN.md, phase P1
   Project rules: CLAUDE.md
   GitHub backend: none (a practice copy: both branches are in the local mirror `origin`)
   Rulings: none
   Plan records: none
   Code map: none
   ```
3. Review, test and change nothing yourself, and send no other agent. When the reviewer answers,
   reply with its answer exactly as it gave it, with nothing before or after it.
