# Plan-only PR

Read by the manager skill before it dispatches, reviews or resumes a plan-only PR (the phase split,
end-of-run bookkeeping, or a Decided move that must land first).

Phase id `plan`, branch `phase/plan-<slug>`
(or the designated branch). The implementer gets the exact plan text to write as its `Plan change`
field — it replaces the usual status and record edits; the reviewer gets the same text and judges
that the diff writes exactly that, touches nothing else, and doesn't contradict the approved goal,
scope or binding decisions. For a large split, where writing the text yourself would mean reading
the plan and docs, the `Plan change` may instead be a specification file outside the repo: per new
phase its id, title, objective, scope, `Depends on`, risk, acceptance intent, validation and the
binding decisions it cites, taken only from the plan and the owner's words. The implementer drafts
the plan edit from it; the reviewer gets the same file and judges that the draft realizes it, adds
no scope, decision or acceptance beyond it, gives every phase an objective, scope, `Depends on`,
risk, acceptance and validation, has nothing in the specification without a source in the plan or
the owner's words, and touches nothing else. You verify only facts (changed files are the plan). A
resumed plan-only PR gets a fresh specification file. Models: the strategy's cheapest allowed
choice. Otherwise the normal loop applies. A resumed plan-only PR keeps none of its own decision or
model records: write its Plan change again from the plan on the default branch and this
conversation's owner answers only.
