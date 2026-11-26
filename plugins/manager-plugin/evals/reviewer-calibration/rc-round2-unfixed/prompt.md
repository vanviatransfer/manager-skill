---
description: Reviewer calibration case for ports, phase P1 (Port parsing)
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
   Base SHA: ae5ff49e6527b56e44879ce01a02a0d60bd10247   Candidate SHA: 6ff0fe8fac277d054599c70518f778fe59cd1f29
   Living plan: docs/LIVING_PLAN.md, phase P1
   Project rules: CLAUDE.md
   GitHub backend: none (a practice copy: both branches are in the local mirror `origin`)
   Rulings: none
   Plan records: none
   Previous blockers: B1. parse_port accepts 0 and 65536, outside the valid range 1-65535
   Code map: none
   ```
3. Review, test and change nothing yourself, and send no other agent. When the reviewer answers,
   reply with its answer exactly as it gave it, with nothing before or after it.
