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
| Merged? | `gh pr view <n> --json state,mergeCommit` | `pull_request_read` `method: get` → `merged: true`, `merge_commit_sha` |
| PR diff | `git diff <base-sha>..<head-sha>` (both) | same; `pull_request_read method: get_diff` only if the head can't be fetched |

Field names map: `headRefOid` ⇔ `head.sha`, `headRefName` ⇔ `head.ref`, `baseRefName` ⇔ `base.ref`,
`mergeCommit.oid` ⇔ `merge_commit_sha`, `state: MERGED` ⇔ `merged: true`.

The pin is not optional on either backend: always pass `--match-head-commit` / `expectedHeadSha`.
A merge refused because the head moved means the review is stale → back to review.

MCP results are facts from GitHub just like `gh` output; a subagent's prose is still a claim.

## Cloud / remote session constraints

- **Designated branch.** A cloud session is often given one development branch it may push to
  (stated in its system prompt / instructions). If so, every phase uses that branch name instead of
  a per-phase branch. Phases are sequential, so this works: after a phase's PR merges, restart the
  branch from the fresh default branch (`git fetch origin <default> && git checkout -B <branch>
  origin/<default>`, then `git push --force-with-lease -u origin <branch>` — safe because it holds
  only merged history) before the next implementer starts. Never stack a new phase on a merged PR's
  branch without that reset, and never reuse a merged PR: each phase opens a new one.
- **Shallow clones.** Cloud checkouts may be shallow. Before diffing `base..head`, fetch both refs
  (`git fetch origin <default> <head-branch>`); fetch with a bounded `--depth` if a merge-base is
  missing rather than `--unshallow`.
- **Subagents** inherit the same tools. Tell them which backend to use and, for MCP, that the tools
  may need loading via ToolSearch first.
