# Final report

Read by the manager skill when no ready phase is left, before the final report (**Stop
conditions**).

Plan records still unpersisted (an owner's answer, a status correction) → first
`references/owner-decisions.md`, **Plan records**: the end-of-run bookkeeping PR.

Before the final report, read the Risks section of a phase's report file only when its short
return's `Risks:` line is not `none` (the working-notes line step 2 keeps).
Final report, compact: phases landed (PR, merged SHA); phases blocked and why; the model strategy
used and any model concerns; the plugin version; by the retro switch's line (step 0 item 1):
`on` → the run record path, or that no record was written and why; `off` → nothing about a
record; a switch never read in this run → say so;
the vault and code map (set up, set up now, or not and why); the self-training skills' `due` and
`check` lines (`references/self-training-due.md`); session-check
recommendations not already given at the gate; one line on repo-enabled plugins, MCP servers or
skills found in step 0 (names, "disable for this repo if unneeded") and any fallback dispatch
(`manager-plugin:fallback` or `general-purpose`); unresolved risks (including validation the
reviewer could not run); decisions answered but not yet persisted, if any; non-blocking notes
carried forward; the default branch's final head SHA; with the improvement pass on, its
`İyileştirme önerileri` section or its one line (read `references/improvement-pass.md` first);
then the
numbered batch of unresolved owner decisions.

End of run, first: a clean shared checkout not at `origin/<default>` → `git switch --detach
origin/<default>`, if the project rules allow switching it.

Ending a turn to wait for the owner (decision batch, final report), add one line: answering
after more than about 50 minutes → run `/compact` now, or answer in a new session.
