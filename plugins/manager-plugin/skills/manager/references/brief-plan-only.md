# Plan-only PR

Read when the dispatch has a `Plan change` field.

**Implementer.** The PR holds exactly the Plan change, nothing else (a specification: draft from
it, adding no scope, decision or acceptance beyond it). The phase-PR plan, vault and skill-record
edits and the code-map build don't apply. Plan text you draft is in English (owner quotes stay
verbatim, in the owner's words); don't translate unchanged text unless the Plan change says so.

**Reviewer**, instead of the phase-PR review: blocker if the diff isn't exactly the Plan change (a
specification: the draft doesn't realize it, adds scope, decisions or acceptance beyond it, lacks
a phase's objective, scope, `Depends on`, risk, acceptance or validation, or the specification
holds content with no source in the plan or the owner's words), touches anything else, or
contradicts the plan's goal, scope or binding decisions. No `<code map> check`.
