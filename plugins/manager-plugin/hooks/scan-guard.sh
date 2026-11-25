#!/bin/sh
# manager-plugin PreToolUse hook for Bash, PowerShell, Glob and Grep: refuses a recursive scan of
# a filesystem root, a drive root or the home folder (`find /`, `ls -R C:\`, `rg x ~`,
# `Get-ChildItem C:\ -Recurse`, `cmd /c dir /s C:\`, also wrapped in `bash -c`, `powershell
# -Command`, chains and substitutions; with no path when the cwd is such a root; Glob or Grep
# there): exit 2, one `manager-plugin:` line on stderr naming the runnable code-map and
# skilltrain commands and a search limited to the repository. Such a scan can run for hours and
# exhaust memory. PreToolUse fires inside subagents too. It has no off switch (`"search_nudge":
# false` turns off the nudge, not this). For an allowed recursive scan in Bash not under
# `timeout` it prints, once per session, a non-blocking hint to prefix `timeout 120`.
# Plain POSIX sh; the logic is scan_guard.py beside the code-map script, run only when the input
# names Glob, Grep or a scan command. It finds Python as the code-map skill does (python3,
# python, py -3) and passes it and the plugin folder, as the search nudge's wrapper does. Without
# Python, a small fallback: refuse a `find` whose first path is exactly a root spelling, with a
# message naming the repository-limited search only. Any other error: exit 0 (fail open).

input=$(cat) || exit 0
command -v grep >/dev/null 2>&1 || exit 0
words='(find|ls|du|tree|e?grep|fgrep|rg|ag|ack|fd|fdfind|where|get-childitem|gci|dir)'
printf '%s' "$input" |
  grep -Eiq '"(Grep|Glob)"|(^|[^A-Za-z0-9_.-]|\\[nt])'"$words"'([^A-Za-z0-9_-]|$)' || exit 0
script="${0%/*}/../skills/code-map/scripts/scan_guard.py"
root=${CLAUDE_PLUGIN_ROOT:-}
case "$root:$0" in
  :/*) root="${0%/*}/.." ;;
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
# No Python: refuse only `find [-H|-L|-P]... [--] <root>` in the raw JSON input (a JSON string
# escapes a backslash as \\ and a quote as \").
case "$input" in
  *'"command"'*) ;;
  *) exit 0 ;;
esac
pre='(^|[^A-Za-z0-9_.-]|\\[nt])find( +-[HLP])*( +--)? +(\\"|'"'"')?'
root_re='(/|/[A-Za-z]|/cygdrive/[A-Za-z]|/mnt/[A-Za-z]|[A-Za-z]:|~|\$HOME|\$\{HOME\}|/home|/Users|/root|[A-Za-z]:(/|(\\\\)+)Users)'
post='(/|(\\\\)+)?(\\"|'"'"')?([ ;|&)"]|$)'
printf '%s' "$input" | grep -Eq "$pre$root_re$post" || exit 0
printf '%s %s %s\n' \
  'manager-plugin: scan refused: a find over a filesystem root, drive root or home folder can run' \
  'for hours and exhaust memory; search only the repository instead: `rg <term> <repo path>` or' \
  '`find <repo path> -name <x>` (`timeout 120` in front of a long one).' >&2
exit 2
