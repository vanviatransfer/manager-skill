# Improvement pass

Read by the manager skill before the final report when the run's improvement pass is on
(`references/model-strategy.md`, **Applying**; pointed to by `references/final-report.md`), and
again after a compaction until that report: when the pass runs, its dispatch, where its output
goes. The pass's suffix on the strategy lines is defined in `references/model-strategy.md`.

The pass is one read-only Opus reviewer agent that looks at everything the run landed and suggests
improvements. It is opt-in and off by default; off → nothing here applies, and the final report
says nothing about it. It is purely additive: on or off, every strategy (all Opus, all Sonnet or
mixed) gives each phase's implementer and reviewer exactly the model and effort it gives without
the pass (**Applying**); the pass only adds its own dispatch at the end.

**When.** Once per run: after the last ready phase is closed and any end-of-run bookkeeping PR
(`references/owner-decisions.md`, **Plan records**) has landed, before the final report; only
when at least one phase PR (not a setup or plan-only PR) landed in this run. None landed → no
dispatch, and the final report says so in one line. The working-notes line `Run <id>: improvement
pass: start <sha>` records its state: any later state (`dispatched`, `done`, `failed`) means it
has already run in this run (before a compaction, or before the owner's answers to the decision
batch continued the run) → never dispatch it again.

**Range.** `<start>..<final>`: `<start>` from that line; `<final>` = `origin/<default>` after
`git fetch origin`. The line lost → `<start>` = the first parent of the earliest merge commit on
the default branch whose PR body carries this run's `Run:` id; neither found → don't dispatch, say
so in one line.

**Dispatch.** Change the line to `Run <id>: improvement pass: dispatched — <start>..<final>`.
Measure the
**Ignored-data guard** before and after (`references/dispatch.md`). One Agent call:
`subagent_type: manager-plugin:reviewer`, `model: opus`, `effort: high`,
`run_in_background: false`, the prompt `Read and follow <the resolved path of
${CLAUDE_SKILL_DIR}/references/brief-improvement.md>.` and that brief's dispatch fields:
`Notes carried forward` are the run's non-blocking review notes (the working-notes line), never a
reviewer's whole review or an implementer's report. Before and after the call, note `git
rev-parse HEAD` and `git status --short --untracked-files=no` of the shared checkout: a change is
an unresolved risk in the final report (never restore anything yourself).

**Result.** The reviewer agent has no Write tool, so the items come in its final answer, not in
a file. Change the line to `done — <n> items, <t> tokens` (the token use the Agent tool's
completion notice gives) or `failed: <one-line reason>`. Failed: the dispatch errored, the agent
type is unavailable, the agent ended with no answer, or its answer lacks the items list. No retry,
no second dispatch, no fallback agent: one line in the final report and continue. A verdict line
in the answer is ignored: the pass gates nothing.

**Output.** The final report gets a section `İyileştirme önerileri`: each item in one line, in the
owner's language (rank, the problem or action, `file:line`, value and cost), copied from the agent's
answer, then what it did not check and the pass's token use. Nothing goes into the plan
automatically and nothing blocks or changes merged work: the owner picks items, and a picked item
becomes a phase only through the normal plan route (a plan-only PR from the owner's words, or the
`living-plan` skill).
