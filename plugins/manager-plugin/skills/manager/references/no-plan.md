# No plan

Read by the manager skill only at step 0 when there is no living plan, or the remaining work is
not split into phases.

No living plan → the run can't start: hand over to the `living-plan` skill (owner-driven, with its
own approval), then begin this skill again from step 0.
Remaining work not split into phases → split it and land the split as a **plan-only PR** before
any phase starts, so every phase exists at its base SHA.
