#!/bin/sh
# manager-plugin SessionStart hook: when the code-map rules block in AGENTS.md or CLAUDE.md at the
# top of the session's repository is older than this plugin's template (its begin marker carries a
# lower version, or none and the block's text differs from the template), print one line on
# stdout, which Claude Code adds to the session's context. The line is information, not an order:
# it names the `codemap.py rules-hint` command that updates the block and says a manager run does
# this in its setup PR. Silent everywhere else (no repository, no block, a current block, an
# unversioned block with the template's text). Plain POSIX sh; it finds Python as the code-map
# skill does (python3, python, py -3), reads those two files only, writes nothing and fails open
# (exit 0, no output) on any error.

input=$(cat) || exit 0
script="${0%/*}/../skills/code-map/scripts/codemap.py"
[ -f "$script" ] || exit 0
for c in python3 python "py -3"; do
  out=$(printf '%s' "$input" |
    PYTHONDONTWRITEBYTECODE=1 $c "$script" session-hook --python "$c" 2>/dev/null) && {
    case "$out" in
      manager-plugin:*) printf '%s\n' "$out" ;;
    esac
    exit 0
  }
done
exit 0
