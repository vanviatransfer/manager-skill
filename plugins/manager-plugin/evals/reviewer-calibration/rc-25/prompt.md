---
description: Review of pull request 1 in a practice repository (rc-25)
tags: [reviewer-calibration-hard]
runs: 1
model: sonnet
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Agent, Bash, Read, Glob, Grep, ToolSearch]
---
Have the plugin's reviewer review pull request #1 of this practice repository, then give me its
answer.

1. `git config eval.reviewerbrief` prints the absolute path of the plugin's reviewer brief;
   check that the file exists. Take this repository's absolute path from `pwd`.
2. Send one `manager-plugin:reviewer` agent, in the foreground, exactly this message with the two
   paths filled in, nothing else:

   ```
   Read and follow <the reviewer brief's absolute path>.
   Project: <this repository's absolute path> (shared checkout), default branch main
   PR: #1, head branch phase/P1
   Base SHA: 924d41f970260292fc9193c6587f2e04ceb33603   Candidate SHA: 88d3f9ea57e6c824dd6c4cca6ae251de88d05f8b
   Living plan: docs/LIVING_PLAN.md, phase P1
   Project rules: CLAUDE.md
   GitHub backend: none (a practice copy: both branches are in the local mirror `origin`)
   Rulings: none
   Plan records: none
   Code map: none
   ```
3. Review, test and change nothing yourself, and send no other agent. When the reviewer answers,
   reply with its answer exactly as it gave it, with nothing before or after it.
