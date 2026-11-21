#!/bin/sh
# manager-plugin PreToolUse hook for Bash: before a `git commit`, in a repository whose
# .codemap.json has "commit_check": true, block the commit while the code map is stale, or while
# its rebuilt pages are not staged (exit 2, one line on stderr telling the model to rebuild the
# map and `git add` its pages, each as a command of its own: the hook runs before the command
# starts, so it does not see what is chained in front of the commit). Off unless a repository
# opts in. Plain POSIX sh; it finds Python as the code-map skill does (python3, python, py -3)
# and fails open (exit 0) when there is no Python, no opt-in, or any error. It writes nothing.

input=$(cat) || exit 0
case "$input" in
  *commit*) ;;
  *) exit 0 ;;
esac
script="${0%/*}/../skills/code-map/scripts/codemap.py"
[ -f "$script" ] || exit 0
for c in python3 python "py -3"; do
  err=$(printf '%s' "$input" | PYTHONDONTWRITEBYTECODE=1 $c "$script" claude-hook --python "$c" 2>&1 >/dev/null)
  status=$?
  case "$status:$err" in
    0:*) exit 0 ;;
    2:codemap:*) printf '%s\n' "$err" >&2; exit 2 ;;
  esac
done
exit 0
