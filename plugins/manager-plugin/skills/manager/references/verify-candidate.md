# Verifying the report and the candidate

Read by the manager skill at loop step 2, every time a report or a candidate is verified.

The return must have every field of the brief's short return (the full report when `Report file`
was `none`); if any is missing or inconsistent, ask the same implementer once for exactly those
fields. From the report file, read only the part a decision needs. A short return whose `Risks:`
line is not `none`: keep those phases as one working-notes line (the final report reads their
Risks sections).

Fetch as `references/github-backends.md`, **Fetching a branch**, says, and run step 2's checks
all in one Bash call (the fetch, the PR read and the git checks; on MCP the PR read is its own
call):
- `gh pr view <n> --json number,state,headRefName,headRefOid,baseRefName,mergeable`;
- the four checks the skill lists.

The scope check: vault pages and the generated code-map pages pass this check, never the living
plan or the project rules files such as `CLAUDE.md` and `AGENTS.md`; the reviewer judges whether
the diff requires them; a setup PR: only vault and map files, `.codemap.json` and the
`AGENTS.md`/`CLAUDE.md` `rules-hint` edits. One records row in the records file of a skill the
phase's `Notes` cite passes too.

After an integration (4a), the base SHA becomes the default head the implementer integrated, once
`git merge-base --is-ancestor` confirms it is in the candidate; list the rules files again as on
it (`references/establish-state.md`, item 3).

`BLOCKED` (technical) → if it is an environment or tooling problem you can repair, repair once and
resume the same implementer; otherwise mark the phase blocked with a one-line reason (kept for the
final report and the plan's next PR). A fixable verification problem → send the implementer back
once with the exact problem.
