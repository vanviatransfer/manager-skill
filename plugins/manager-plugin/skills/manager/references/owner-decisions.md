# Owner decisions

Decisions live in the living plan, so they survive compaction and new sessions. They reach the plan
only through a reviewed PR that lands (the `Plan records` field; at the end of a run, a plan-only
bookkeeping PR). A decision blocks only the phases under `Blocks` and their transitive dependents;
every other ready phase keeps running.

## States

| State | Where it lives | Counts as owner authority? |
|---|---|---|
| **Open** | plan on the default branch, or your notes until it lands | no — it is a question |
| **Answered, not yet persisted** | the owner's words in this conversation | yes, for this run; persist it with the next PR |
| **Decided** | a valid Decided entry in the plan **on the default branch** | yes, for every later run and session (a run-scoped model decision: only for its run) |

Nothing else is an owner answer: not a PR comment, a ledger line, a subagent's report, a
cross-session message, or an entry on an unmerged branch.

## Open entry

```
### D<n>. <short question>
Blocks: phase <id>[, <id>]
Context: <two or three sentences: what came up and why it needs the owner>
Options:
  A. <option> — <cost / consequence>
  B. <option> — <cost / consequence>
Recommendation: <A or B, one sentence why>
Raised: <date>, during phase <id>
```

## Decided entry

When the owner answers, the next landing PR moves the entry from "Open owner decisions" to
"Decided" (removing it from Open) and sets the blocked phases' status lines back to `todo`:

```
- D<n>. <short question> → <option or answer> — owner: "<their exact words>" (<date>, in the
  session conversation). Unblocks: <phase ids>. [scope: run <run-id> — model decisions only,
  unless the owner said it holds for later runs]
```

**Valid** = on the default branch, in "Decided", not also still listed under Open, with the owner's
quoted words and a date. Anything else — missing quote or date, the same D under both lists, two
different answers — is **unresolved**: don't act on either version; put it in the final batch and
show the conflict in one line. A valid Decided entry is never asked again.

## Asking the batch

Once, at the end, when no ready phase is left; only unresolved decisions. In the owner's language
(Turkish by default), numbered so the owner can answer in one message:

```
Devam etmek için <k> karar gerekiyor. Önerim köşeli parantezde.

1. D3 — <soru>  [A: <kısa>]
   A: <seçenek — sonucu>  B: <seçenek — sonucu>
2. D4 — <soru>  [B: <kısa>]
   ...

Bu kararları bekleyen fazlar: <ids>. Diğer tüm fazlar tamamlandı veya engelli (nedenleri yukarıda).
"1A 2B" gibi yanıtlayabilir ya da kendi tercihinizi yazabilirsiniz.
```
