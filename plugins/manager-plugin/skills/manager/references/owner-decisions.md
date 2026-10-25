# Owner decisions

Keep open decisions in the living plan, in one section, so they survive compaction and new
sessions. Add entries through the current phase's PR (or the next one).

```
## Open owner decisions

### D<n>. <short question>
Blocks: phase <id>[, <id>]
Context: <two or three sentences: what came up and why it needs the owner>
Options:
  A. <option> — <cost / consequence>
  B. <option> — <cost / consequence>
Recommendation: <A or B, one sentence why>
Raised: <date>, during phase <id>
```

When the owner answers, move the entry to a "Decided" list with their words quoted and the date,
unblock the phases, and continue.

## Asking the batch

Ask once, all together, numbered so the owner can answer in one message:

```
<k> decisions are needed to continue. My recommendation is in brackets.

1. D3 — <question>  [A: <short>]
2. D4 — <question>  [B: <short>]
...

Phases blocked until then: <ids>. Everything else is done or in progress.
You can answer like "1A 2B", or write your own.
```
