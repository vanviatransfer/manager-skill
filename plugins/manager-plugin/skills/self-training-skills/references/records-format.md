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
with the same context, and it keeps the date of the use (not the day it was resolved); the latest
row for a context is its current state. A row must start and end with `|` and have all five
cells, with a real `YYYY-MM-DD` date and one of the outcomes above. Nothing but blank lines may
follow the table. `check` reports every line that breaks this (file:line), and `stats` skips a
line that isn't a row and says so. No secrets or personal data.

Each Train changelog entry records `records: <n>`, the row count it consumed; the rows after that
count are "since the last training".
