#!/bin/sh
# manager-plugin SessionStart (startup, resume, clear, compact) and SubagentStart hook: in a
# repository that uses the plugin (a .codemap.json, a manager-plugin rules marker in AGENTS.md or
# CLAUDE.md, or a marked self-training skill), adds one line to the session's or the subagent's
# context: the absolute, runnable `codemap.py query` and `skilltrain.py query` commands, and
# never to search the disk for them (an agent that doesn't know where a plugin script is tends
# to scan the whole disk for it). JSON `hookSpecificOutput.additionalContext`; silent elsewhere.
# The argument is the event. Plain POSIX sh; the logic is `scan_guard.py start`. It finds Python
# as the code-map skill does (python3, python, py -3), writes nothing and fails open (exit 0, no
# output) on any error.

input=$(cat) || exit 0
# This script's folder: $0 up to its last / or \ (Git Bash on Windows may pass C:\...\x.sh).
here=${0%[/\\]*}
script="$here/../skills/code-map/scripts/scan_guard.py"
[ -f "$script" ] || exit 0
root=${CLAUDE_PLUGIN_ROOT:-}
case "$root:$0" in
  :/* | :[A-Za-z]:[/\\]* | :\\\\*) root="$here/.." ;;
esac
# A python3 or python under WindowsApps (often a Microsoft Store stub, slow to fail) is
# tried only last (`+`), after `py -3`.
for c in python3 python "py -3" +python3 +python; do
  case "$c:$(command -v "${c#+}" 2>/dev/null)" in
    +*[/\\][Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss][/\\]*) c=${c#+} ;;
    +* | *[/\\][Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss][/\\]*) continue ;;
  esac
  out=$(printf '%s' "$input" | CODEMAP_NUDGE_PYTHON="$c" CODEMAP_NUDGE_ROOT="$root" \
    PYTHONDONTWRITEBYTECODE=1 $c "$script" start "${1:-SessionStart}" 2>/dev/null) && {
    case "$out" in
      '{"hookSpecificOutput"'*) printf '%s\n' "$out" ;;
    esac
    exit 0
  }
done
exit 0
