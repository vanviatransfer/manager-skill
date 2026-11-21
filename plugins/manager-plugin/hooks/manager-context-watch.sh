#!/bin/sh
# manager-plugin PostToolUse hook for subagent spawns (Agent / Task tool): watches the
# orchestrator's own context during a manager run. When the session has a run marker
# (~/.claude/manager-runs/active/<session id>, which the manager skill writes and removes) and its
# context crosses the budget (the last request, as the end of the transcript in the hook input
# records it, held more tokens than the budget, and the request before it that called the Agent
# or Task tool held no more), it adds one line to the context: make sure the run's notes file
# (~/.claude/manager-runs/notes/<session id>.md) is current, without printing the notes, and
# suggest `/compact` to the owner once, at the next stop. So it speaks once per crossing, not
# after every return above the budget; no such earlier request in the transcript's end → it
# speaks, as for a first crossing. Stateless. The budget is 200,000 tokens; the environment
# variable MANAGER_CONTEXT_BUDGET sets another (no `.codemap.json` setting).
# Silent everywhere else: no marker for this session, a subagent's own tool call, a context at or
# under the budget or already over it at the previous Agent call, no transcript or no request in
# its end, no HOME, no Python. The notes folder holds no marker: only active/ is looked at.
# Plain POSIX sh: without any run marker on this machine it ends here, before Python starts. The
# logic is context_watch.py beside the manager skill's usage.py, run with the Python the code-map
# skill's rule finds (python3, python, py -3). It reads the hook input, the marker folder and the
# transcript's end, writes nothing and fails open (exit 0, no output) on any error.

input=$(cat) || exit 0
[ -n "${HOME:-}" ] || exit 0
runs="$HOME/.claude/manager-runs/active"
set -- "$runs"/*
[ -e "$1" ] || exit 0
script="${0%/*}/../skills/manager/scripts/context_watch.py"
[ -f "$script" ] || exit 0
for c in python3 python "py -3"; do
  out=$(printf '%s' "$input" | PYTHONDONTWRITEBYTECODE=1 $c "$script" "$runs" 2>/dev/null) ||
    continue
  [ -z "$out" ] || printf '%s\n' "$out"
  exit 0
done
exit 0
