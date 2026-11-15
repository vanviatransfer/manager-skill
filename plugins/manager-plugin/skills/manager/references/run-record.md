# Run record

Read by the manager skill before the run record's first write in a run, and again after a
compaction. Bold section names are the manager skill's.

So that runs can be compared and the skill improved from evidence (`manager-retro` skill), keep a
compact record of each run in the owner's home directory, shared by all projects on this machine and
outside every repository: `~/.claude/manager-runs/<YYYY-MM-DD>-<repo>-<run-id>.md`, where `<repo>`
is the bare repository name (no owner, no slash). Write it through Bash (`mkdir -p
~/.claude/manager-runs` once, then append with `>>`), which resolves `~` on every platform. Never
spend a tool call on it alone: put the write at the front of the next Bash command you run anyway,
separated by `;` (`printf '%s\n' '<line>' >> <file>; <your command>`, with no `'` inside the line),
so that command's exit status stays its own; an error from the append is not that command's failure
(then follow the skip rule). Only the final `summary:` line may need a call of its own. If it can't
be written, skip the record and say so in the final report; in a cloud session it may not persist
after the session. After a compaction, find the file by this run's id. Append one line per phase
outcome (landed or blocked) with the next Bash command after it, so an interrupted run still leaves
its data, and never repeat a phase-and-outcome already listed (a phase blocked and later landed gets
both lines). Append a `summary:` line when the run stops; if it continues, append a new one: the
last `summary:` line is the current one. You tag each reported blocker with a generic class (see
below). Format:

```
# <repo> <run-id> · plugin <version> · model strategy: <strategy>
phase | risk | model impl/rev | rounds | impl tokens | review tokens per round | verdicts | blocker classes | skipped (when:) | fallback
<one line per phase; tokens from the Agent tool's usage output (a resumed agent's delta), else unknown>
summary: phases landed <n>, blocked <n>; tokens impl <n> (+<k> unknown) | unknown, review <n> (+<k> unknown) | unknown; compactions <n>; owner questions <n>; usage change <n | unknown>
```

In the `summary:` line, each token total is the sum of the known values in this file's phase
lines (for review, every round's value), followed by the count of unknown ones (`tokens impl
1840000 (+3 unknown)`); write `unknown` only when no value is known. A later line for a phase
already listed (blocked, then landed) records only the tokens spent since its earlier line, so
nothing is counted twice. The file holds only the header, the column line, phase lines and
`summary:` lines: no free-text notes. Progress, open work and decisions go in the living plan and
the review ledger, not here.

Blocker classes are short generic tags (e.g. `locking`, `pii`, `validation-gap`, `plan-record`),
never names of products, vendors, customers or code. Apart from the repository name and the model
strategy in the header, record numbers and tags only: no secrets, code, file contents or the
owner's words.
