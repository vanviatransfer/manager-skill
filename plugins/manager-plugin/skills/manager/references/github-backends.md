# GitHub backends

The skill talks to GitHub through one of two backends. Pick once in step 0, record it in one line,
and pass the same choice to every subagent brief.

## Choosing

1. **`gh`** — run `gh auth status`. If it exits 0 and is logged in to the project's host, use `gh`.
   This is the normal case on a local machine.
2. **GitHub MCP** — otherwise, look for the `mcp__github__*` tools (in cloud / remote sessions they
   are usually deferred: load them with ToolSearch, e.g.
   `select:mcp__github__pull_request_read,mcp__github__list_pull_requests,mcp__github__create_pull_request,mcp__github__merge_pull_request`).
   If they load, use MCP. This is the normal case in a Claude Code cloud session, where `gh` may be
   installed but not authenticated.
3. **Neither** → environment failure. Report it (stop condition); don't fall back to raw `curl`
   against the API and don't ask for a token.

An installed `gh` is not an authenticated `gh`. Decide on `gh auth status`, not on `which gh`.
If `gh` fails with an auth error mid-run, switch to MCP if it's available and say so in one line.

`git` itself (fetch, diff, show, worktree, push) works the same in both backends; only GitHub API
operations differ. Owner/repo come from `git remote get-url origin`.

## Operation map

| Operation | `gh` | GitHub MCP |
|---|---|---|
| Open PRs | `gh pr list --state open` | `list_pull_requests` `state: open`, `fields: [number,title,head,base,draft]` |
| PR facts | `gh pr view <n> --json number,state,headRefName,headRefOid,baseRefName,mergeable,files` | `pull_request_read` `method: get` → `state`, `merged`, `head.ref`, `head.sha`, `base.ref`, `mergeable`; files: `method: get_files` |
| Create PR | `gh pr create --base <default> --head <branch> --title … --body …` | `create_pull_request` `base`, `head`, `title`, `body` |
| Merge, pinned | `gh pr merge <n> --<method> --match-head-commit <sha>` | `merge_pull_request` `merge_method: <method>`, `expectedHeadSha: <sha>` |
| Merged / closed PR for a branch | `gh pr list --state closed --head <branch> --json number,headRefOid,mergedAt` (`mergedAt` null = closed unmerged) | `list_pull_requests` `state: closed`, `head: <owner>:<branch>`, `fields: [number,merged,merged_at,head]` → keep `merged_at` set, compare `head.sha` |
| Candidate contains default? | `git merge-base --is-ancestor origin/<default> <sha>` (both) | same |
| Fast-forward-only landing | `git push origin <sha>:refs/heads/<default>` (no force; refused unless a fast-forward) — only where the project lands this way and the session may push the default | same |
| Landed tree = reviewed tree? | `git diff --quiet <reviewed-sha> <merge-commit>` (both) | same |
| Merged? | `gh pr view <n> --json state,mergeCommit` | `pull_request_read` `method: get` → `merged: true`, `merge_commit_sha` |
| PR diff | `git diff <base-sha>...<head-sha>` (both) | same; `pull_request_read method: get_diff` only if the head can't be fetched |
| Allowed merge methods | `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed` | not mapped: use the project rules and the merge call's refusal |
| Review-ledger comment | `gh pr comment <n> --body …` | `add_issue_comment` `issue_number: <n>`, `body` |
| Read ledger | `gh pr view <n> --json comments` | `pull_request_read` `method: get_comments` |
| Remote ref now | `git ls-remote origin <ref>` (both) | same |

Field names map: `headRefOid` ⇔ `head.sha`, `headRefName` ⇔ `head.ref`, `baseRefName` ⇔ `base.ref`,
`mergeCommit.oid` ⇔ `merge_commit_sha`, `state: MERGED` ⇔ `merged: true`.

The pin is not optional on either backend: always pass `--match-head-commit` / `expectedHeadSha`.
A merge refused because the head moved means the review is stale → back to review.

MCP results are facts from GitHub just like `gh` output; a subagent's prose is still a claim.

## Cloud / remote session constraints

- **Designated branch.** A cloud session is often given one development branch it may push to
  (stated in its system prompt). If so, every phase uses that branch instead of `phase/<id>-<slug>`.
  Phases are sequential, so this works, but after each merge the branch must be reconciled with the
  new default head before the next implementer starts. Never stack a new phase on a merged PR's
  history unreconciled, and never reuse a merged PR: each phase opens a new one.
  1. Confirm the remote branch still points at the merged PR's head:
     `git ls-remote origin <branch>` = reviewed SHA. If the ref is gone (the repo auto-deletes
     merged head branches) and the PR is confirmed merged, recreate it with a plain push:
     `git push origin origin/<default>:refs/heads/<branch>`, and skip steps 2–3. A ref present at
     any other SHA is unexplained drift → stop using the branch and report it; never overwrite
     commits you didn't land.
  2. If the project rules allow force-pushing this branch (or say nothing against it):
     `git fetch origin <default> && git checkout -B <branch> origin/<default>`, then
     `git push --force-with-lease=<branch>:<reviewed-sha> origin <branch>`. Always give the explicit
     expected SHA: a bare `--force-with-lease` after a `git fetch` checks against the just-fetched
     ref and protects nothing.
  3. If the project forbids force-pushes or history rewrites, don't reset: `git checkout -B
     <branch> origin/<branch> && git merge origin/<default>` and push normally (a fast-forward
     when the merge method kept the branch's commits). The next PR then diffs only new work. A
     merge conflict is not yours to resolve: report it. If the project also forbids merge commits
     on the branch, or merges by rebase (the next PR would replay the old commits), landing
     further phases from this branch is blocked: report it as an environment constraint (owner
     decision); don't look for another way around the rule.
- **Shallow clones.** Cloud checkouts may be shallow. Before diffing `base...head`, fetch both refs
  (`git fetch origin <default> <head-branch>`); fetch with a bounded `--depth` if a merge-base is
  missing rather than `--unshallow`.
- **Subagents** inherit the same tools. Tell them which backend to use and, for MCP, that the tools
  may need loading via ToolSearch first.
