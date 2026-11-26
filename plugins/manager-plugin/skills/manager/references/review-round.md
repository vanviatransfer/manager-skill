# Review round

Read by the manager skill at loop step 3, before every reviewer dispatch, and before a
review-ledger line posted elsewhere (an integration round, a phase with a PR that blocks): the
pre-dispatch checkout, the reviewer's extra fields, verdict checks, the brake, two retries, the
ledger, the notes.

## Before dispatch

The shared checkout should be on the candidate with a clean tree (`git rev-parse HEAD` =
candidate, `git status --short` empty), so the reviewer can validate there. If it isn't:
1. a live implementer → ask it once to leave the checkout so; still not so → 2 or 3;
2. no implementer (resumed PR, can't be resumed) or step 1 failed, and the tree is clean →
   `git switch --detach <candidate>` yourself, only if the project rules allow switching the
   shared checkout;
3. otherwise (dirty tree — never discard anyone's changes — or the move is forbidden) → give the
   reviewer a worktree if the project allows one; else don't dispatch: block that landing and
   record why as an unresolved risk.

Note both values. The reviewer's dispatch fields also carry: a worktree location only if the
project allows worktrees; the rulings and plan records the implementer got.

## The verdict

- `Validation`: a `when:` command reported `not required` with a reason from the diff counts as
  satisfied.
- `Checkout untouched`: New untracked files are acceptable only if the reviewer listed them as
  created by its validation (it deletes them); remove any still present, each by its listed path,
  never recursively through a link. A worktree it reports left in place goes into the final
  report's unresolved risks; don't remove it yourself.

**Same blockers twice** (the brake) holds when a re-review's `Previous blockers` are all `still
present as B<k>` and cover all its blockers (ledger: `same`); untagged → compare titles.

`Not checked` never blocks by itself; anything listed there goes into the final report's unresolved
risks.

Clean-tree route only: if the reviewer reports tracked files changed by its validation, the result
is invalid (`not run`). Restore them from the repo root with `git restore --staged --worktree :/`,
then retry the validation once, in a worktree if the project allows one, else block as below.
Never restore or remove anything on a tree that was dirty before the review.

**Validation `not run`**: fix the cause (usually the checkout state), redo the pre-dispatch
check, note both values again, and resume the **same** reviewer (SendMessage) with the candidate
unchanged, to run only the missing validation and re-report the full verdict. If it can't be
resumed, dispatch a new reviewer. If the validation still can't run, block that landing and record
it as an unresolved risk.

**No review**: redo the pre-dispatch check and dispatch one new reviewer; if that also fails, an
environment failure for this phase: move on to independent work.

## The ledger and the notes

The **review-ledger** PR comment: `review-ledger <run-id> round <k>: <verdict | INTEGRATE> at
<sha>; blockers: <B<n> titles | none>[; same]`; `<k>` counts every ledger line; an integration
round posts `INTEGRATE` at the candidate it integrates. When a phase with a PR blocks (owner
decision, tripped brake), add one ledger line `review-ledger <run-id> blocked: <Dn | reason>`.

Non-blocking notes go to the next relevant phase's brief (lean notes only
to a phase whose scope covers that file) or the plan's notes; never a fix round of their own.
