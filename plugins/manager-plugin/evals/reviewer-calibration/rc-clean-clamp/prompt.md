---
description: Reviewer calibration case for bounds, phase P1 (Clamp)
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
   Base SHA: 188cd90ca4a1b27fd1aed87b5493b29374762bdc   Candidate SHA: 319e4c17eebcfd8ec680a636ec6b72e6fd38ca5b
   Living plan: docs/LIVING_PLAN.md, phase P1
   Project rules: CLAUDE.md
   GitHub backend: none (a practice copy: both branches are in the local mirror `origin`)
   Rulings: none
   Plan records: none
   Code map: none
   ```
3. Review, test and change nothing yourself, and send no other agent. When the reviewer answers,
   reply with its answer exactly as it gave it, with nothing before or after it.
