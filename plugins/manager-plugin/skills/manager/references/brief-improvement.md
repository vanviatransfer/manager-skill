# Improvement pass brief

Read when the dispatch's first line names this file: a manager run's end-of-run improvement pass
(`improvement-pass.md`, beside this file). One reviewer agent, read-only on the project, at most
one pass per run. This is no PR review: no verdict, no `Reviewed SHA`, no ledger.

## Dispatch fields (only these)

```
Read and follow <this file's path>.
Project: <repo path>, default branch <default>
Living plan: <path>
Project rules: <the path of every rules file | none>
Run: <run-id>
Range: <default head at the run's step 0>..<default head now>
Notes carried forward: <the run's non-blocking review notes | none>
Code map: <python command and quoted codemap.py path | none>
```

## Instructions

You review what one manager run landed and suggest what would improve it most. You don't
implement, review a PR, give a verdict or spawn subagents; use no skills or MCP tools.

1. **Read** the `Project rules` files first (as on the range's end). Of the plan, as on the
   range's end (`git show <end>:<plan-path>`), read only its goal, its constraints and its binding
   decisions, by heading (`grep -n '^#'`), and the sections of the phases the range's PRs name.
2. **The range.** `git log --oneline <range>`, `git diff --stat <range>`, then the diff. Too large
   to read whole (more than about 3000 changed lines or 40 files): work from `git diff
   --name-only <range>` and the riskiest files (most changed, least tested, the ones touching
   security, data, money or concurrency, the ones the notes name), and say so in your answer.
   With a `Code map` command, `<code map> impact` and `query` may point to callers outside the
   diff.
3. **Read-only.** In the project checkout: no edit, commit, push, branch switch, `stash`, `reset` or
   `clean`, no PR, issue or comment. Run the project's validation commands and small probes only in
   a scratch clone outside every repository (`git clone --no-hardlinks <project> <dir>`, then `git
   -C <dir> switch --detach <end>`). Never copy, link or read the checkout's git-ignored data into
   it, and install nothing that needs credentials. Remove that clone, and only it, at the end. You
   write nothing else.
4. **Look for** defects in the landed changes (an unmet acceptance criterion, a bug, a security
   or data-safety issue, a rule breach, a missing test) and improvements specific to this project
   and its workflow (tests, checks, plan, docs, process). Prefer what you verified (ran or read
   the code path) over what you suspect.
5. **Report** in your final answer (you have no Write tool; write no file): at most 7 items,
   ranked by value. Each item: the problem or opportunity; `file:line`; evidence (what you
   ran or read, tagged `[code-verified]`, `[measured]` or `[inference]`); one concrete action;
   rough value (high, medium, low) and cost (small, medium, large). No "for awareness" items,
   nothing cosmetic, and nothing that only repeats a carried-forward note (one that adds evidence
   names the note). Fewer items, or none, is a valid result. End with what you did not check.
6. **Answer** with only: first the list, one line per item, `<n>. <problem or action> —
   <file:line> — value <v>, cost <c>`; then each item's full entry (problem, evidence, action);
   then `Not checked: <one line>`. Nothing else: no verdict line, no preamble.
