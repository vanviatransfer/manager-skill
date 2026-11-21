# Establishing state

Read by the manager skill at step 0, at the start of every run (a new session included) and again
after a compaction: the detail of its items 1, 3 and 5. Item 3's rules-files list is read again
when loop step 1 or step 2 lists the rules files again.

## Item 1: the plugin copy

Note the plugin version (`version` in `${CLAUDE_SKILL_DIR}/../../.claude-plugin/plugin.json`, if
it resolves) for the final report. Check that both brief files, the six `brief-*.md` files and
`github-backends.md` beside them exist: a missing one means an incomplete plugin copy (environment
failure: report it).

## Item 3: the project rules and the plan

The rules are every rules file the repository has: `CLAUDE.md`, `AGENTS.md`, `.claude/CLAUDE.md`,
`.claude/rules/*.md` and the files they import with `@path`. Keep their paths as one working-notes
line: it is the `Project rules` field of every dispatch, both roles (`none` when there is no such
file). The plugin's agents set `omitClaudeMd`, which drops the whole instruction block, so a
subagent knows only the rules files that field lists.

The field lists the rules files as on that dispatch's Base SHA, so the line is taken again
whenever the base moves: a landing may add, remove or rename a rules file. Loop step 1 lists them
as on the phase's base SHA when the default head has moved since the line was taken, and step 2
as on the new base after an integration; replace the working-notes line with the result. The
files a commit has (then the files those import with `@path`):

```
git ls-tree -r --name-only <base-sha> -- CLAUDE.md AGENTS.md .claude/CLAUDE.md .claude/rules
```

Ask once if the plan's location isn't obvious. Of the plan, read the headings and every phase's
`Status`, `Depends on` and `Risk` lines:

```
git show origin/<default>:<plan-path> | grep -nE '^(#|(Status|Depends on|Risk):)'
```

and only these parts: binding decisions, open and decided owner decisions, the model-strategy
record, the fix-round limit. No phase's section is read here: a phase's section is read when the
phase is scheduled (loop step 1), as on its base SHA. Read the rest only when a decision needs it.

## Item 5: in-flight work

- open PR → that phase resumes at loop step 2, checking the Git/PR facts only (there is no
  report, and its Plan records are unknown: send the reviewer `unknown (resumed)`), with base
  SHA = `git merge-base origin/<default> <headRefOid>`; first read the PR's review-ledger
  comments (`gh pr view <n> --json comments`; MCP: `pull_request_read` `method: get_comments`):
  the fix-round and integration counts (**Brakes**) and any `blocked` entry come from them, the
  rounds of earlier sessions included, never from memory or from the commits; then a fresh
  review; a ledger PASS is never a reason to skip it, and a ledger `blocked` entry keeps the
  phase parked unless the decision behind it is now decided; loop step 1 is skipped, so first
  read the phase's section as on that base SHA (the `plan.py` command in the implementer brief's
  step 1, or its `awk`): step 2's scope check needs it;
- a remote `phase/*` branch or the designated branch with no open PR: look up closed PRs for
  it (`gh pr list --state closed --head <branch> --json number,headRefOid,mergedAt`). Head =
  a merged PR's head → landed work, at most a designated branch still to reconcile (loop step
  5). Head = a PR closed unmerged → abandoned: report it, don't resume it (a new attempt at that
  phase uses a fresh branch name; on a designated branch, report it). Otherwise, if it has
  changes against the default (`git diff --stat origin/<default>...origin/<branch>`), that
  phase resumes from the branch (the implementer opens the PR), not from scratch;
- work on a designated branch from an earlier session that this session can't push to →
  report it; don't resume or duplicate it;
- PRs merged but the phase not marked done → mark it done in the next PR;
- an open plan-only PR (`phase/plan-*`) → resume it like a phase if its Plan change is still
  needed; otherwise report it rather than open a duplicate;
- an open setup PR (`setup/code-map*`, or `Setup: code map` work on the designated branch) →
  resume it like a plan-only PR if step 6 still needs it; else report it, untouched (on a
  designated branch it occupies the branch: stop, as **Sequential phases** says);
- an open PR that matches no phase → say so; don't touch it.
