#!/bin/sh
# manager-plugin PreToolUse hook for Bash, PowerShell, Glob and Grep: refuses a recursive scan of
# a filesystem root, a drive root or the home folder (`find /`, `ls -R C:\`, `rg x ~`,
# `Get-ChildItem C:\ -Recurse`, `cmd /c dir /s C:\`, also wrapped in `bash -c`, `eval`,
# `powershell -Command` or `-EncodedCommand`, chains and substitutions; with no path when the cwd
# is such a root; Glob or Grep there): exit 2, one `manager-plugin:` line on stderr naming the
# runnable code-map and skilltrain commands and a search limited to the repository. Such a scan
# can run for hours and exhaust memory. PreToolUse fires inside subagents too. It has no off
# switch (`"search_nudge": false` turns off the nudge, not this). For an allowed recursive scan in
# Bash not under `timeout` it prints, once per session, a non-blocking hint to prefix
# `timeout 120`. Plain POSIX sh; the logic is scan_guard.py beside the code-map script, run only
# when the input names Glob, Grep, a scan command or a PowerShell -EncodedCommand. It finds Python
# as the code-map skill does (python3, python, py -3) and passes it and the plugin folder, as the
# search nudge's wrapper does. Without Python, a small fallback: refuse a `find` whose first path
# is exactly a root spelling, with a message naming the repository-limited search only. Any other
# error: exit 0 (fail open).

input=$(cat) || exit 0
command -v grep >/dev/null 2>&1 || exit 0
words='(find|ls|du|tree|e?grep|fgrep|rg|ag|ack|fd|fdfind|where|get-childitem|gci|dir|forfiles)'
# Also a PowerShell -EncodedCommand (-e, -ec, -enc...): its base64 script names no scan word.
enc='[[:space:]]-e[a-z]*[[:space:]]+[\\"'"'"']*[A-Za-z0-9+/]{16}'
printf '%s' "$input" |
  grep -Eiq '"(Grep|Glob)"|(^|[^A-Za-z0-9_.-]|\\[nt])'"$words"'([^A-Za-z0-9_-]|$)|'"$enc" ||
  exit 0
# This script's folder: $0 up to its last / or \ (Git Bash on Windows may pass C:\...\x.sh).
here=${0%[/\\]*}
script="$here/../skills/code-map/scripts/scan_guard.py"
root=${CLAUDE_PLUGIN_ROOT:-}
case "$root:$0" in
  :/* | :[A-Za-z]:[/\\]* | :\\\\*) root="$here/.." ;;
esac
if [ -f "$script" ]; then
  for c in python3 python "py -3"; do
    out=$(printf '%s' "$input" | CODEMAP_NUDGE_PYTHON="$c" CODEMAP_NUDGE_ROOT="$root" \
      PYTHONDONTWRITEBYTECODE=1 $c "$script" 2>/dev/null)
    status=$?
    case "$status:$out" in
      0:'{"hookSpecificOutput"'*) printf '%s\n' "$out"; exit 0 ;;
      0:*) exit 0 ;;
      2:manager-plugin:*) printf '%s\n' "$out" >&2; exit 2 ;;
    esac
  done
fi
# No Python: refuse only `find [-H|-L|-P]... [--] <root>` at the start of a command (or after
# ; & | ( ` or a newline) in a Bash call's "command" value, taken from the raw JSON input (a JSON
# string escapes a backslash as \\ and a quote as \"); a PowerShell call or any other field is
# never matched.
printf '%s' "$input" | grep -Eq '"tool_name"[[:space:]]*:[[:space:]]*"Bash"' || exit 0
cmd=$(printf '%s' "$input" |
  grep -Eo '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' 2>/dev/null) || exit 0
cmd=${cmd#\"command\"}
[ -n "$cmd" ] || exit 0
pre='(^[[:space:]]*:[[:space:]]*"|[;&|(`]|\\n)[[:space:]]*find( +-[HLP])*( +--)? +(\\"|'"'"')?'
root_re='(/|/[A-Za-z]|/cygdrive/[A-Za-z]|/mnt/[A-Za-z]|[A-Za-z]:|~|\$HOME|\$\{HOME\}|/home|/Users|/root|[A-Za-z]:(/|(\\\\)+)Users)'
post='(/|(\\\\)+)?(\\"|'"'"')?([ ;|&)"]|$)'
printf '%s' "$cmd" | grep -Eq "$pre$root_re$post" || exit 0
printf '%s %s %s\n' \
  'manager-plugin: scan refused: a find over a filesystem root, drive root or home folder can run' \
  'for hours and exhaust memory; search only the repository instead: `rg <term> <repo path>` or' \
  '`find <repo path> -name <x>` (`timeout 120` in front of a long one).' >&2
exit 2
