# Recurring blocker class

Read by the manager skill when reviewers report the same class of defect (e.g. lock ordering,
personal data exposed to the client) in two phases of a run.

Propose what would prevent it, as an
ordinary owner decision (`D<n>`, asked in the batch, blocking no phase). If the class is mechanical
(a fixed pattern a linter, type check or test can catch), option A is that check: the command, where
it fails today (its cost), and which phase adds it and fixes those failures: a later phase whose
scope covers the check's setup (config, dependency, script) and those failures, or a new phase if
the owner picks one (added to the plan through a plan-only PR). A prose rule (exact text) is for
judgement calls, or option B. You only propose it. Once decided, it lands as a new binding decision
(`B<n>`) through the next PR's `Plan records`, or, if no PR would land before the adding phase
starts, a plan-only PR whose `Plan change` is that `B<n>` and its `D<n>` Decided move: the rule
text, or for a check "phase <id> adds <command> and fixes the failures it finds at its base inside
its scope (any outside it → NEEDS_OWNER_DECISION); it is required validation for that phase and for
every phase whose base contains its merge". Dispatch the adding phase only from a base that holds
that `B<n>`. Implementers and reviewers read all of the plan's binding decisions, so later phases
apply it. Moving it into the project rules file is the owner's call.
