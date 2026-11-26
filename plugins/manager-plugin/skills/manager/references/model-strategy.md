# Model strategy

Read by the manager skill at the gate (step 0 item 6) of every run, again after a compaction
(**Applying** gives every later dispatch its `model` and `effort`), and when a phase needs more
model than the strategy allows. The run, its id and the working-notes strategy line are defined in
the skill's **Model strategy**.

A new session is always a new run, even when it resumes interrupted work; a recorded `run`
strategy is never applied by inference.

**Which strategy applies** (first match):
1. A strategy the owner gave in this conversation for this run — including, on a resume, words
   that adopt the recorded one ("aynı modelle devam") — and, after compaction, the working-notes
   line as the notes file (or, without one, the summary) carries it.
2. After a compaction that lost that line: the plan's `run` record on the default branch, only if
   its id equals this run's id as the notes file or the summary carries it. Otherwise **ask** —
   never fall back to a standing policy for a run already under way.
3. A new run: a `standing` strategy recorded in the plan on the default branch.
4. Otherwise ask — this gate is mandatory and separate from ordinary owner decisions. When the
   session resumes interrupted work and the plan holds a `run` record, recommend that recorded
   strategy.

**Asking.** After the read-only part of step 0, assess complexity from the remaining phases'
headings and `Risk` lines alone (step 0 reads no phase's section) — or, with no plan yet, from the
owner's request; don't read source. Recommend Sonnet, Opus or a mixed strategy, ask in Turkish, and
end the turn:

```
Bu çalışma için önerim: <Sonnet | Opus | Karma: standard → Sonnet, critical → Opus, işaretsiz → standard>.
Gerekçe: <tek cümle: doğruluk riski, karmaşıklık, tahmini token tüketimi ve maliyet>.
[Bu konuşmada ilgisiz işler var: yeni oturumda başlamanızı öneririm; devir notu gerekmez, "planı manager ile devam ettir" yazın (manager dışı yarım iş için not alın)]
[Başlamadan önce önerim: `/autocompact 300k` çalıştırın[ (şu an <değer>)]; cc-plugin-you-should-know'ı kapatın]
[Bu projede kullanılmayacak görünen sunucular: <adlar>. Kapatmak için (yalnız bu projede, sonraki oturumdan itibaren): `/mcp disable <ad>` · geri açmak: `/mcp enable <ad>`]
[Bu repoda vault yok. Bu repoda sürekli çalışacaksanız kurmanızı öneririm: projenin mimarisi, modülleri, işletimi, entegrasyonları, terimleri ve alınmış kararlar ile gerekçeleri kalıcı sayfalara yazılır, kod haritası kurulur; oturumlar (ajanlar dahil) her seferinde baştan aramak yerine bunları okur. Kısa süreli bir repoysa gerek yok. Kurayım mı? Evet / Bu sefer hayır / Hayır, bu repoda bir daha sorma]
[Haritayı commit'te güncel tutayım mı? (Claude Code commit kontrolü; git kancası için komut veririm) Evet / Hayır]
[Python yok; kurayım mı? (`<komut>`) Hayır: harita kullanılmaz.]
Sonda Opus iyileştirme turu (tek ajan, salt okunur, öneriler rapora; ~100–200k token): Evet / Hayır
Model tercihiniz hangisi?
```

The bracketed lines only when they apply (unrelated earlier work in this conversation, the session
check, no vault, a setup PR to make, no Python), with only the items found. An install answer is
carried out right after the gate.

**Improvement pass** (opt-in, default off): one Opus pass at the end of the run
(`references/improvement-pass.md`). It is on only when the owner says yes to its line at the gate
or otherwise in this conversation for this run, when rule 3's `standing` line ends with
`; improvement pass: on`, or, after a compaction, when the working-notes strategy line (rule 2: the
plan's `run` line) ends so or a `Run <id>: improvement pass:` line for this run is kept. Anything
else is off: no answer, a strategy given without that line being
asked, a line without the suffix. Never inferred.

Guide for the recommendation: Sonnet for bounded code, docs, tests and ordinary reviews; Opus for
architecture, numerical or financial correctness, concurrency, security-critical code or hard
debugging. Default to mixed by the plan's `Risk` field: `standard` phases Sonnet for both roles,
`critical` phases Opus for both, unmarked phases standard — say all three in the question.
Recommend Opus throughout only when most remaining
phases are critical. Opus costs more per token; say so when you recommend it.

**Applying.** The approved strategy fixes, per role (and per phase or condition for a mixed one),
the `model` and the `effort` (`medium`, a `critical` phase's reviewer `high`, unless the strategy
or the owner says otherwise). It covers every dispatch
of the run: phases, fix rounds, integrations, plan-only PRs, brake retries. Record it in the plan
(**Plan records**, first PR of the run; for every run, also one under a standing policy) as
`Model strategy: <strategy> — scope: run <run-id> — owner: "<quote>" | standing (<date>)`,
replacing the previous `run` line. A `standing` line (`scope: standing`) is written only when the
owner says the choice is a policy for all runs, and stays until the owner changes it.

Both lines, and the working-notes line, may end with `; improvement pass: on` or
`; improvement pass: off`; absent (every older record) means off. The `run` line and the
working-notes strategy line always carry it; a `standing` line only when the owner's policy words
cover the pass. Pass on → also keep the
working-notes line `Run <id>: improvement pass: start <the default head step 0 item 2 recorded>`.
The pass's own dispatch is outside the strategy: `model: opus`, `effort: high`, by the owner's yes.

**Not enough model.** If a phase needs stronger reasoning than the strategy allows (it is in an
Opus category, or a brake tripped and a stronger model is the remedy), don't escalate. Run it under
the strategy if that is still sound and list the concern as a risk; otherwise mark it blocked on a
model decision (an ordinary owner decision, `D<n>`, asked in the final batch) and continue other
work. The owner's answer to such a decision amends the strategy for that phase only, and only in
the run where it was asked (its Decided entry carries `scope: run <id>`; a later run ignores it in
favour of its own gate), unless the owner says it holds for later runs; a new run's approved
strategy doesn't silently settle an open model decision. A mixed strategy's condition that the plan
and the owner's words don't settle for a phase (e.g. "Opus if it handles CSP input") is such a
model decision too: block that phase on it, picking neither model.
