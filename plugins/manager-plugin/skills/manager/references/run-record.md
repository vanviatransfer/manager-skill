# Run record

Read by the manager skill before the run record's first write in a run, and again after a
compaction.

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
phase | risk | model impl/rev | rounds | impl context | review context per round | verdicts | blocker classes | skipped (when:) | fallback
<one line per phase; contexts from the Agent tool's usage output (`subagent_tokens`), else unknown>
summary: phases landed <n>, blocked <n>; context impl <n> (+<k> unknown) | unknown, review <n> (+<k> unknown) | unknown; compactions <n>; owner questions <n>
```

`subagent_tokens` is an agent's context size at its last request, not cumulative usage: a size,
not a bill. `impl context` is the implementer's value at its last return in the phase (after a
rotation, each implementer's, joined by `+`); `review context per round` is each round's
reviewer's. Records written before plugin 0.8.3 call these columns `impl tokens` and `review
tokens per round` (`tokens impl` in the summary): the same figures.

In the `summary:` line, each context total is the sum of the known values in this file's phase
lines (for review, every round's value), followed by the count of unknown ones (`context impl
1840000 (+3 unknown)`); write `unknown` only when no value is known. A later line for a phase
already listed (blocked, then landed) records only what came since its earlier line (new agents'
values; for an implementer resumed across both, its growth), so
nothing is counted twice. The file holds only the header, the column line, phase lines and
`summary:` lines: no free-text notes. Progress, open work and decisions go in the living plan and
the review ledger, not here.

Blocker classes are short generic tags (e.g. `locking`, `pii`, `validation-gap`, `plan-record`),
never names of products, vendors, customers or code. Apart from the repository name and the model
strategy in the header, record numbers and tags only: no secrets, code, file contents or the
owner's words.
