# No report from an implementer

Read by the manager skill at loop step 2 when an implementer ends with no report at all (an error,
a crash or a usage limit).

Resume it once. If that
fails, judge from facts, not its last words. `git fetch origin <branch>`, then the shared checkout:
a dirty tree (whoever left it) or local commits on no remote ref (`git log --oneline HEAD
--not --remotes`; also `<branch>` if it exists locally) → never discard them; every phase shares
this checkout, so stop the run and report it (**Stop conditions**). Otherwise, the remote branch
and the PR:
- an open PR whose head is a new candidate (not the one last reviewed) → step 2's fact checks,
  then a fresh review (previous blockers by title, as in 4b);
- a remote branch with no open PR, or one whose head was already reviewed → a replacement
  implementer on it (its own step 3 continues from the remote branch), with its `Fix round` field
  if it ended mid fix round (4b);
- no remote branch → nothing was delivered: restart step 1 (new base SHA = current default head).
At most one such replacement or restart per phase: if that agent also ends with no report, do the
same checkout check, then treat the phase as an environment failure (move on to independent work,
unless **Sequential phases** says stop). A usage limit that persists is an environment failure
(**Stop conditions**), not a reason to keep dispatching.
