# Run record

Read by the manager skill before the run record's first write in a run, and again after a
compaction, only while the retro switch is on.

**Retro switch.** The run record is opt-in: the owner turns it on once with
`/manager-plugin:manager-retro on` (and off with `off`), which writes a flag file,
`manager-plugin/retro` in the Claude config folder (`$CLAUDE_CONFIG_DIR`, else `~/.claude`),
user-level and outside every repository; `MANAGER_RETRO=on` or `off` in the environment overrides
the file (a cloud environment, where the file doesn't persist). The default is off.
`sh "${CLAUDE_SKILL_DIR}/scripts/retro.sh"` (step 0, so after a compaction too; it only reads)
prints `on` or `off` and what decided it. Only `on` starts or continues a record. Anything else,
an error or no output included → write no run record and run no `usage.py` in this run. Never turn
the switch on or off yourself, and never delete or change a record an earlier run wrote, whatever
the switch says.

So that runs can be compared and the skill improved from evidence (`manager-retro` skill), keep a
compact record of each run in the owner's home directory, shared by all projects on this machine and
outside every repository: `~/.claude/manager-runs/<YYYY-MM-DD>-<repo>-<run-id>.md`, where `<repo>`
is the bare repository name (no owner, no slash). Write it through Bash (`mkdir -p
~/.claude/manager-runs` once, then append with `>>`), which resolves `~` on every platform. Never
spend a tool call on it alone: put the write at the front of the next Bash command you run anyway,
separated by `;` (`printf '%s\n' '<line>' >> <file>; <your command>`, with no `'` inside the line),
so that command's exit status stays its own; an error from the append is not that command's failure
(then follow the skip rule). Only the final `summary:` line may need a call of its own. If it can't
be written, skip the record and say so in the final report; in a cloud session it may not outlive
the session. After a compaction, find the file by this run's id. Append one line per phase outcome
(landed or blocked) with the next Bash command after it, so an interrupted run still leaves its
data, and never repeat a phase-and-outcome already listed (a phase blocked and later landed gets
both lines). Append a `summary:` line when the run stops, and a new one after any phase line written
after it: the last `summary:` line is the current one. Tag each reported blocker with a generic
class (below). Format:

```
# <repo> <run-id> · plugin <version> · model strategy: <strategy>
phase | risk | model impl/rev | rounds | impl context | review context per round | verdicts | blocker classes | skipped (when:) | fallback
usage | agent | role | model | requests | input | cache read | cache write 5m | cache write 1h | output | context at return | warm resumes | cold resumes | seconds
<one line per phase; contexts from the Agent tool's usage output (`subagent_tokens`), else unknown>
<`usage` lines, as `scripts/usage.py` prints them (Usage lines, below)>
summary: phases landed <n>, blocked <n>; context impl <n> (+<k> unknown) | unknown, review <n> (+<k> unknown) | unknown; compactions <n>; owner questions <n>
```

`subagent_tokens` is an agent's context size at its last request, not cumulative usage. `impl
context` is the implementer's value at its last return in the phase (after a rotation, each
implementer's, joined by `+`); `review context per round` is each round's reviewer's. Numbers are
integers (`193000`, not `193k`) or `unknown` (never `?`); `rounds` counts the phase's reviews;
verdicts in full (`PASS WITH NOTES`).

In the `summary:` line, each context total is the sum of the known values in this file's phase
lines (for review, every round's value), followed by the count of unknown ones (`context impl
1840000 (+3 unknown)`); write `unknown` only when no value is known. A later line for a phase
already listed (blocked, then landed) records only what came since its earlier line (new agents'
values; for an implementer resumed across both, its growth), so
nothing is counted twice. The file holds only the header, the two column lines, phase lines,
`usage` lines and `summary:` lines: no free-text notes. Progress, open work and decisions go in
the living plan and the review ledger, not here.

Blocker classes are short generic kebab-case tags, no spaces (`locking`, `pii`, `validation-gap`,
`plan-record`), never names of products, vendors, customers or code. Apart from the repository name
and the model strategy in the header, record numbers and tags only: no secrets, code, file contents
or the owner's words.

## Usage lines

A script reads this session's transcripts (writing nothing) and prints one `usage` line per agent,
in the `usage` columns above: `<python> "${CLAUDE_SKILL_DIR}/scripts/usage.py" <session id>
<agent>[=<model>]... >> <file>`. `<python>` is the Python as the code-map skill's rule picks it
(none → no `usage` lines; say so in the final report); `<session id>` is the name of the **Run
marker** file; an `<agent>` is an agent id as the Agent tool returned it, or `orchestrator` for you;
`=<model>` (subagents only): the strategy's model.

- With a phase's line, in front of the same Bash command: that phase's agents (every implementer
  and every round's reviewer), so an interrupted run still leaves them.
- Before each `summary:` line, in the same Bash call and before the marker is removed:
  `orchestrator --since <the **Run marker** file>`. Its line then counts the run, from the
  moment that file was written (never write it twice), not the session before it. No marker
  file → no `orchestrator` line; say so in the final report.
- An id you no longer hold (a compaction): leave it out. Always name the agents: with none, the
  script prints every subagent of the session, another run's and other work's included.

A later line for the same agent replaces its earlier one (an implementer resumed after its phase's
line, a run that continues). In a line, `agent` is that id or `orchestrator`, `role` the agent's
type (yours: `main`) and `model` its last request's, ending `!=<model>` when a request ran on
another. `requests` counts its API requests; `input` (uncached), `cache read`, `cache write 5m` and
`cache write 1h` (by cache lifetime) and `output` are token sums over them, each priced differently.
`context at return` is the figure `subagent_tokens` reports. `warm resumes` and `cold resumes` count
the requests sent 60 seconds or more after the agent's previous one: cold when the cache had expired
and the context was written again, warm when it was read; a compaction's first request is neither. A
subagent's are only those a message to it started (a resume): a request that follows a tool call is
none, however long the call took. Yours count those too (a wait for a subagent, a long command),
beside the owner's prompts. `seconds` runs from the agent's first record to its last (yours: from
the marker's time): a reviewer's is how long the review took. `unknown` marks what the transcripts
don't show.
