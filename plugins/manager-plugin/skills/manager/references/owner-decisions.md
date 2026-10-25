# Owner decisions

Keep open decisions in the living plan, in one section, so they survive compaction and new
sessions. An entry reaches the plan through the next PR that lands (usually the next phase's; at
the end of a run, a plan-only bookkeeping PR). Until then, keep it in your working notes for the
final batch.

A decision blocks only the phases listed under `Blocks` and their transitive dependents. Every
other ready phase keeps running.

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

When the owner answers, move the entry to the "Decided" list with their words quoted and the date
(through the next PR), unblock the phases, and continue. Only the owner's own words in this
conversation count.

## Asking the batch

Once, at the end, when no ready phase is left. In the owner's language (Turkish by default),
numbered so the owner can answer in one message:

```
Devam etmek için <k> karar gerekiyor. Önerim köşeli parantezde.

1. D3 — <soru>  [A: <kısa>]
   A: <seçenek — sonucu>  B: <seçenek — sonucu>
2. D4 — <soru>  [B: <kısa>]
   ...

Bu kararları bekleyen fazlar: <ids>. Diğer tüm fazlar tamamlandı veya engelli (nedenleri yukarıda).
"1A 2B" gibi yanıtlayabilir ya da kendi tercihinizi yazabilirsiniz.
```
