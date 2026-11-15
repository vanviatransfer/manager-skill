# Landing branches

Read by the manager skill at loop step 4a when the landing keeps the branch's commits (rebase
merge, fast-forward push), when no integration method is permitted, when the project lands by
fast-forward only, or when the landed tree differs from the reviewed one.

- **Linear history** (step 3, before Yes/No). When the landing keeps the branch's commits (rebase
  merge, fast-forward push) and the project requires linear history or merges by rebase, the
  commits above the default head must also be linear (`git rev-list --merges
  origin/<default>..<reviewed-sha>` empty); a non-linear candidate there is blocked, not
  integrated again. A squash landing needs no linear branch.
- **No permitted integration** (e.g. rebase merges or a linear fast-forward landing where the
  project forbids force-pushes, or a fast-forward-only default the session can't push) → decide
  this before dispatching anything: block that landing, record why, continue independent work.
- **Fast-forward-only landing.** A fast-forward-only project lands by its own rule, typically `git
  push origin <reviewed-sha>:refs/heads/<default>` without force (refused unless it is a
  fast-forward; a refusal because the default just moved is a race → back to 3, not a block).
- **Landed tree differs.** `git diff --quiet <reviewed-sha> <merge-commit>` showing a different
  tree means the default moved during the merge — report it to the owner as an incident at once,
  block the phase's dependents, and have a fresh reviewer validate the landed tree (base = the
  merge commit's first parent, candidate = the merge commit; judge the combined tree, not the plan
  records of the commits that raced in); never fix it silently. A PASS there unblocks the
  dependents; anything else is an owner decision (a revert or fix is the owner's call).
