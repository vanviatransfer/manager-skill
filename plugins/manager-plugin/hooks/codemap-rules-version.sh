#!/bin/sh
# manager-plugin SessionStart hook: when the code-map rules block in AGENTS.md or CLAUDE.md at the
# top of the session's repository is older than this plugin's template (its begin marker carries a
# lower version, or none and the block's text differs from the template), print one line on stdout,
# which Claude Code adds to the session's context. The line is information, not an order: it names
# the `codemap.py rules-hint` command that updates the block and says a manager run does this in its
# setup PR. Silent everywhere else (no repository, no block, a current block, an unversioned block
# with the template's text). Plain POSIX sh; it finds Python much as the code-map skill does
# (python3, python, py -3; on Windows, a python3 or python under WindowsApps is tried last, after
# py -3), reads those two files only, writes nothing and fails open (exit 0, no output) on any
# error.

input=$(cat) || exit 0
# This script's folder: $0 up to its last / or \ (Git Bash on Windows may pass C:\...\x.sh).
here=${0%[/\\]*}
script="$here/../skills/code-map/scripts/codemap.py"
[ -f "$script" ] || exit 0
# A python3 or python under WindowsApps (often a Microsoft Store stub, slow to fail) is
# tried only last (`+`), after `py -3`.
for c in python3 python "py -3" +python3 +python; do
  case "$c:$(command -v "${c#+}" 2>/dev/null)" in
    +*[/\\][Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss][/\\]*) c=${c#+} ;;
    +* | *[/\\][Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss][/\\]*) continue ;;
  esac
  out=$(printf '%s' "$input" |
    PYTHONDONTWRITEBYTECODE=1 $c "$script" session-hook --python "$c" 2>/dev/null) && {
    case "$out" in
      manager-plugin:*) printf '%s\n' "$out" ;;
    esac
    exit 0
  }
done
exit 0
