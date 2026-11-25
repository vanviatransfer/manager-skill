#!/bin/sh
# manager-plugin PreToolUse hook for Grep, Glob and Bash: "map first". In a repository whose
# .codemap.json has a "map" (and no "search_nudge": false), it blocks the first broad search of a
# session once (exit 2, one line on stderr: run the code map's `query` first, then repeat the
# search); every later search is allowed. Plain POSIX sh; the logic is search_nudge.py beside the
# code-map script, run only when the input names Grep, Glob or a search command. It finds Python
# as the code-map skill does (python3, python, py -3) and fails open (exit 0) on any error. It
# passes that Python and the plugin folder (CLAUDE_PLUGIN_ROOT, else this script's own when its
# path is absolute) so the message can name the runnable `codemap.py query` command.
# Skills branch (same hook, same fast path): a search that targets skill files (.claude/skills/,
# SKILL.md, lessons.md, */skills/*, a skill's references/, a marked skill's records) in a
# repository with a marked self-training skill is blocked once per session the same way (exit 2,
# one `manager-plugin:` line naming the runnable
# `skilltrain.py query "<repo root>" -- "<term>"`, `--` since a term may start with -), with
# its own state: it neither uses up nor gets the code-map block. It needs no .codemap.json or
# map; `"search_nudge": false` there turns both branches off.

input=$(cat) || exit 0
words='(e?grep|fgrep|rg|ag|ack|find|codemap\.py)'
if command -v grep >/dev/null 2>&1; then
  printf '%s' "$input" |
    grep -Eq '"(Grep|Glob)"|(^|[^A-Za-z0-9_.-]|\\[nt])'"$words"'([^A-Za-z0-9_-]|$)' || exit 0
fi
# This script's folder: $0 up to its last / or \ (Git Bash on Windows may pass C:\...\x.sh).
here=${0%[/\\]*}
script="$here/../skills/code-map/scripts/search_nudge.py"
[ -f "$script" ] || exit 0
root=${CLAUDE_PLUGIN_ROOT:-}
case "$root:$0" in
  :/* | :[A-Za-z]:[/\\]* | :\\\\*) root="$here/.." ;;
esac
for c in python3 python "py -3"; do
  err=$(printf '%s' "$input" | CODEMAP_NUDGE_PYTHON="$c" CODEMAP_NUDGE_ROOT="$root" \
    PYTHONDONTWRITEBYTECODE=1 $c "$script" 2>&1 >/dev/null)
  status=$?
  case "$status:$err" in
    0:*) exit 0 ;;
    2:manager-plugin:*) printf '%s\n' "$err" >&2; exit 2 ;;
  esac
done
exit 0
