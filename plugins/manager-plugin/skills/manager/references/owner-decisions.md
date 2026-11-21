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
Blocks: phase <id>[, <id>] | none (e.g. a proposed rule after a recurring blocker class)
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
  session conversation). Unblocks: <phase ids | none>. [Adds: B<n> — for a decided rule]
  [scope: run <run-id> — model decisions only, unless the owner said it holds for later runs]
```

**Valid** = on the default branch, in "Decided", not also still listed under Open, with the owner's
quoted words and a date. Anything else — missing quote or date, the same D under both lists, two
different answers — is **unresolved**: don't act on either version; put it in the final batch and
show the conflict in one line. A valid Decided entry is never asked again.

A decision that unblocks a phase a brake had blocked: **Brakes** says how that phase's counts
restart.

At step 0 (item 4): phases blocked only by decided decisions become ready; correct their status
lines in the next PR.

## Plan records

New open decisions, Decided moves (owner's exact words, date), new binding
decisions from them, status corrections and the model-strategy record ride the next PR that lands,
as the implementer's `Plan records` field, written by you verbatim; the reviewer gets the same field
and blocks any plan record in the diff that doesn't match it. Before the final report, if anything
is still unpersisted, land one plan-only bookkeeping PR. If no branch or checkout is free for it (a
designated branch holding a blocked phase's work, or a shared checkout holding uncommitted or
unpushed work), the final report is the record instead; say so.

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
