# Open ideas (not started)

Notes only; nothing here is decided or implemented.

## 1. `/autocompact 600000` before a run starts

- Idea: the manager makes sure `/autocompact 600000` has been run before it starts work.
- To check first: the exact syntax and effect of the command; whether the orchestrator can run it
  itself or can only ask the owner to; whether 600000 is a sensible value; how it interacts with
  the existing compaction rules (working-notes lines, run id, re-reading the dispatch fields).

## 2. `cc-plugin-you-should-know` plugin

- Idea: look at it and decide whether the manager plugin should include it or recommend it.
- To answer: does it raise or lower token use (startup load in the main session and in
  subagents, interaction with the tool-restricted `implementer` / `reviewer` agents); advantages
  and disadvantages; license and security; fit with the manager skill.
- Principle: no copying; integrate ideas into the skill only if measured to help.
