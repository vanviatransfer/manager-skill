# Lessons format

`lessons.md` sits beside the worker skill's `SKILL.md` and holds one markdown table; a title line
above it is allowed. Header and separator:

```markdown
| id | lesson | label | evidence | status |
|---|---|---|---|---|
```

- `id`: `L1`, `L2`, ... in order, never reused.
- `lesson`: one sentence.
- `label`, one of:
  - `owner-reported`: an owner verdict (quote it in `evidence`);
  - `observed`: measured here (cite the record dates and contexts);
  - `sourced`: cited, not tested here (cite the vault page, path or document);
  - `hypothesis`: not established yet.
- `evidence`: the records, quotes or sources behind it.
- `status`: `active`, `superseded by L<n>` or `retired`.

Append-only: old rows are never edited except to change their status. A changed lesson is a new
row, and the old one becomes `superseded by L<n>`. A rule in the skill cites only lessons that
aren't `retired`. When a contradiction demotes a lesson to `hypothesis`, add a new row with that
label and supersede the old one.
