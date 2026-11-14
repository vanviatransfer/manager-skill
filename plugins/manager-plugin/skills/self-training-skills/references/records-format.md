# Records format

A records file holds one markdown table; a title line above it is allowed. Header and separator:

```markdown
| date | context | outcome | tags | note |
|---|---|---|---|---|
```

- `date`: `YYYY-MM-DD`, the day of the use.
- `context`: `phase <id>` (a manager phase) or `owner session`.
- `outcome`, one of:
  - `pending-review`: a manager phase, before its review verdict;
  - `pass`: the phase's review passed (PASS or PASS WITH NOTES);
  - `changes-required`: the review asked for changes;
  - `owner-good` / `owner-bad`: the owner's verdict on the output;
  - `failed`: the use failed (validation, a broken run);
  - `n/a`: no verdict.
- `tags`: short lowercase words, comma-separated (blocker classes, the part of the work, and
  `confounded` when more than one thing changed at once).
- `note`: short; the owner's words verbatim when they gave a verdict; domain fields as
  `key=value`. Escape a literal pipe as `\|`.

Rows are append-only: never edit or delete one. A correction or a resolved verdict is a new row
with the same context; the latest row for a context is its current state. No secrets or personal
data.
