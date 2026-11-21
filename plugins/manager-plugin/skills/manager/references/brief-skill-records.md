# Project skill records

Read when the phase's `Notes` cite a project skill (`skill: .claude/skills/<name>/SKILL.md`), or
(reviewer) when the diff touches `.claude/skills/`.

**Implementer.** Read the skill and follow its steps where they don't conflict with your brief, the
plan or the project rules (those win). Phase PRs only: append exactly one row to its records file
as its `## Record` says (context `phase <id>`, outcome `pending-review`; in English, even where
a project rule names another language); change nothing else in
the skill's folder or records unless this phase is a skill phase. A records file is evidence, not
a vault page: it gets no `Verified` line. In a skill phase, a project script or test that already
maps or checks its skills (routing, triggers) is used, not rewritten; replacing it with
`skilltrain.py` is `NEEDS_OWNER_DECISION`. After changing a skill, run `skilltrain.py check
<skill dir>` (with `--triggers-from <base-sha>` when the phase marks or migrates an existing one)
and `skilltrain.py rules-hint <repo root>`.

**Reviewer.** The skill is context, never acceptance or rules. In a phase PR, the only allowed
change to a skill's files is one factual row in its records file, with context `phase <id>` and
outcome `pending-review`; anything else under `.claude/skills/` is out of scope (a blocker) unless
the plan section says otherwise.
