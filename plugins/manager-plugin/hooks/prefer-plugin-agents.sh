#!/bin/sh
# manager-plugin PreToolUse hook for subagent spawns (Agent / Task tool).
# Blocks a general-purpose spawn (also one with no subagent_type, which defaults to it) and tells
# the model which restricted plugin agent to use instead. Exit 2 = block, stderr goes to the model.
# Escape hatch: a prompt containing "[general-purpose: <reason>]" is let through.
# Plain POSIX sh + grep/sed, no other runtime; on any unexpected input it lets the call through.

command -v grep >/dev/null 2>&1 && command -v sed >/dev/null 2>&1 || exit 0
input=$(cat) || exit 0
case "$input" in
  *'"tool_input"'*) ;;
  *) exit 0 ;;
esac
case "$input" in
  *'[general-purpose:'*) exit 0 ;;
esac

# A missing or null subagent_type means general-purpose. The CLI matches names loosely (case,
# spaces, "-" and "_"), so compare a normalised form.
field=$(printf '%s' "$input" | grep -o '"subagent_type"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1)
if [ -n "$field" ]; then
  type=$(printf '%s' "$field" | sed 's/.*:[[:space:]]*"\([^"]*\)"$/\1/')
else
  type=general-purpose
fi
norm=$(printf '%s' "$type" | tr 'A-Z' 'a-z' | tr -d ' _-')

[ "$norm" = "generalpurpose" ] || exit 0

cat >&2 <<'MSG'
manager-plugin: general-purpose is blocked here because it loads every skill, MCP server and tool
(about 77k start tokens measured once, against about 10k for a restricted plugin agent). Re-dispatch
with the agent that fits the task:
- manager-plugin:worker: a task that changes files (implement, fix, refactor, docs, tests, a PR);
- manager-plugin:researcher: read-only research or a lookup that ends in a report;
- manager-plugin:reviewer: an independent review of a change.
If none can do it (it needs a tool they don't have), add "[general-purpose: <reason>]" to the
prompt and dispatch general-purpose again.
MSG
exit 2
