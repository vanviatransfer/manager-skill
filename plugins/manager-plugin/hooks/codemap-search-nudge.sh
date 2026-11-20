#!/bin/sh
# manager-plugin PreToolUse hook for Grep, Glob and Bash: "map first". In a repository whose
# .codemap.json has a "map" (and no "search_nudge": false), it blocks the first broad search of a
# session once (exit 2, one line on stderr: use the code map's `query` first, then repeat the
# search); every later search is allowed. Plain POSIX sh; the logic is search_nudge.py beside the
# code-map script, run only when the input names Grep, Glob or a search command. It finds Python
# as the code-map skill does (python3, python, py -3) and fails open (exit 0) on any error.

input=$(cat) || exit 0
words='(e?grep|fgrep|rg|ag|ack|find|codemap\.py)'
if command -v grep >/dev/null 2>&1; then
  printf '%s' "$input" |
    grep -Eq '"(Grep|Glob)"|(^|[^A-Za-z0-9_.-]|\\[nt])'"$words"'([^A-Za-z0-9_-]|$)' || exit 0
fi
script="${0%/*}/../skills/code-map/scripts/search_nudge.py"
[ -f "$script" ] || exit 0
for c in python3 python "py -3"; do
  err=$(printf '%s' "$input" | PYTHONDONTWRITEBYTECODE=1 $c "$script" 2>&1 >/dev/null)
  status=$?
  case "$status:$err" in
    0:*) exit 0 ;;
    2:manager-plugin:*) printf '%s\n' "$err" >&2; exit 2 ;;
  esac
done
exit 0
