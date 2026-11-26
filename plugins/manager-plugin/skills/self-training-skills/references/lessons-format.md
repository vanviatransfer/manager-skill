# Lessons format

`lessons.md` sits beside the worker skill's `SKILL.md` and holds one markdown table; a title line
above it is allowed. Header and separator:

```markdown
| id | lesson | label | evidence | status | confidence | last-confirmed |
|---|---|---|---|---|---|---|
```

- `id`: `L1`, `L2`, ... in order, never reused.
- `lesson`: one sentence.
- `label`, one of:
  - `owner-reported`: an owner verdict (quote it in `evidence`);
  - `observed`: measured here (cite the record dates and contexts);
  - `sourced`: cited, not tested here (cite the vault page, path or document);
  - `hypothesis`: not established yet.
- `evidence`: the records, quotes or sources behind it. Cite a **verifier outcome** as a records
  row, `<YYYY-MM-DD> <context>: <outcome>` (e.g. `2026-11-02 phase P3: pass`), where the outcome
  is `pass` or `changes-required` (a review finding), `failed` (a test or validation result) or
  `owner-good` / `owner-bad` (an owner verdict); or an owner verdict from the conversation as
  `owner: "<words>", <YYYY-MM-DD>`. `check` reports a cited row the records don't hold.
- `status`: `active`, `superseded by L<n>` or `retired`.
- `confidence`: `high` (2 or more independent verifier outcomes, i.e. different uses, or an
  owner verdict), `medium` (one), `low` (none).
- `last-confirmed`: `YYYY-MM-DD` of the newest supporting record, or `unknown`.

A rule in the skill cites only lessons that aren't `retired` or `hypothesis`, and whose
`evidence` cites a verifier outcome; a `sourced` lesson may back a rule without one only until the
first training (while the changelog has only its creation entry). `check` reports a rule that
breaks this.

**Stale.** `check` and `stats` print one `stale lesson L<n>` line for an `active` lesson whose
`last-confirmed` is more than 90 days old (`--stale-days N`) or has more than 20 records rows
dated after it (`--stale-uses M`; same-day rows don't count; for `unknown`, every row counts),
whichever comes first. A `last-confirmed` later than today is a problem. Train puts each
one to the owner: keep, re-confirm or retire. The script never retires a lesson.

Append-only: old rows are never edited, with one exception: a status change, or a re-confirmation (a
new supporting record, cited in that training's changelog entry), may update `confidence` and
`last-confirmed` in place, besides `status`. A re-confirmation alone never fixes a "no verifier
outcome" problem: the `evidence` cell is unchanged. A changed lesson is a new row, and the old one
becomes `superseded by L<n>`. When a contradiction demotes a lesson to `hypothesis`, add a new row
with that label and supersede the old one.

**Old tables.** A table with only the first five columns still works: its lessons read as
`confidence` `low` and `last-confirmed` `unknown`, reported once as a `note:` line, not as a
problem; a rule citing a lesson without a verifier outcome, or a cited row the records lack, is a
`note:` line too (a `hypothesis` behind a rule stays a problem). Migrating turns those notes into
problems; the fix is a superseding `observed` row whose evidence cites the records. `<cmd> check
<skill dir> --migrate` adds the two columns in place, filled from each row's evidence and the
records, and leaves every other byte as it was; like any lessons edit, only with the owner's
agreement.
