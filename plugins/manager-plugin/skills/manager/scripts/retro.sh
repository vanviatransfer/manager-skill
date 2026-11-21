#!/bin/sh
# manager-plugin retro switch: whether manager runs keep a run record for the manager-retro skill.
# Off unless turned on.
#   retro.sh [status]   one stdout line: `on` or `off`, then in brackets what decided it
#   retro.sh on         creates the flag file, then prints that line
#   retro.sh off        removes the flag file, then prints that line
# The flag file is <config folder>/manager-plugin/retro, the config folder being $CLAUDE_CONFIG_DIR,
# else ~/.claude: user-level, outside every repository; that it exists is the switch, what it holds
# is not read. MANAGER_RETRO=on or off in the environment overrides the file (a cloud environment,
# where the file does not persist); another value is ignored. `status` only reads; `on` and `off`
# touch that one file (and create its folder), never a run record.
# Plain POSIX sh; `on` needs mkdir, `off` needs rm.
# Exit status: 0; 1 when `on` or `off` could not change the file (the reason on stderr, the line
# still printed); 2 for any other argument (nothing printed on stdout, nothing changed).

if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
  dir=$CLAUDE_CONFIG_DIR/manager-plugin
elif [ -n "${HOME:-}" ]; then
  dir=$HOME/.claude/manager-plugin
else
  dir=
fi
flag=$dir/retro

status() {
  case "${MANAGER_RETRO:-}" in
    [Oo][Nn]) echo 'on (MANAGER_RETRO)'; return 0 ;;
    [Oo][Ff][Ff]) echo 'off (MANAGER_RETRO)'; return 0 ;;
  esac
  if [ -n "$dir" ] && [ -e "$flag" ]; then
    echo 'on (flag file)'
  else
    echo 'off (no flag file)'
  fi
}

fail() {
  echo "retro: $1" >&2
  status
  exit 1
}

[ "$#" -le 1 ] || set -- 'too many arguments'
case "${1:-status}" in
  status)
    status
    ;;
  on)
    [ -n "$dir" ] || fail 'no CLAUDE_CONFIG_DIR and no HOME: nowhere to put the flag file'
    { mkdir -p "$dir" && echo on > "$flag"; } 2>/dev/null || fail "cannot write $flag"
    status
    ;;
  off)
    if [ -n "$dir" ] && [ -e "$flag" ]; then
      rm -f "$flag" 2>/dev/null
      [ ! -e "$flag" ] || fail "cannot remove $flag"
    fi
    status
    ;;
  *)
    echo 'usage: retro.sh [status|on|off]' >&2
    exit 2
    ;;
esac
exit 0
