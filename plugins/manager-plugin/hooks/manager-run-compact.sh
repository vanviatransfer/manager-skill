#!/bin/sh
# manager-plugin PreCompact and SessionStart (matcher `compact`) hook: carries a manager run across
# a compaction. The manager skill writes a marker file, ~/.claude/manager-runs/active/<session id>,
# once the run's model strategy is settled and removes it when the run ends; this hook only
# tests that the file exists for the session in the hook input. The event is the argument:
#   PreCompact    stdout becomes extra instructions for the summary: keep the run's working-notes
#                 lines verbatim (Claude Code cuts a hook's output at 10,000 characters);
#   SessionStart  one stdout line, added to the context after the compaction: re-read the manager
#                 skill and the references whose triggers apply.
# Silent everywhere else: no marker for this session, a subagent's own compaction (the input
# carries an agent id), no session id or one that is not a plain name, no HOME, another argument.
# Plain POSIX sh with grep and sed; it reads the hook input, tests that one path, writes nothing
# and fails open (exit 0, no output) on any error.

input=$(cat) || exit 0
command -v grep >/dev/null 2>&1 || exit 0
command -v sed >/dev/null 2>&1 || exit 0
[ -n "${HOME:-}" ] || exit 0
printf '%s' "$input" | grep -q '"agent_id"[[:space:]]*:[[:space:]]*"' && exit 0
key='"session_id"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9_-]\{1,\}\)"'
id=$(printf '%s' "$input" | sed -n -e "/$key/{" -e "s/.*$key.*/\\1/p" -e q -e '}' 2>/dev/null) ||
  exit 0
[ -n "$id" ] || exit 0
[ -f "$HOME/.claude/manager-runs/active/$id" ] || exit 0

case "${1:-}" in
  PreCompact)
    cat <<'EOF'
manager-plugin: a manager run is in progress in this session. In the summary, under a heading
"Manager working notes", keep every working-notes line of the run verbatim, one per line, each as
it was last written:
- `Run <id>: model strategy ...` and `Run <id>: code map ...`;
- the `Project rules` paths and the Rulings added to every dispatch;
- each `D<n> → <answer>: "<owner's words>"` line (an owner answer not yet persisted) and the plan
  records still to be written;
- each `<phase>: rotated at round <k>` line and the series' PRs;
- the phases whose short return's `Risks:` line is not `none`, the blocked phases with their
  one-line reasons, the non-blocking notes carried forward;
- for the phase in flight: its id, PR number, branch, base SHA and candidate SHA; the
  implementer's agent id, its last `subagent_tokens` and return time; the checkout values noted
  before the review; the last ignored-data measurement; the report file's path.
Keep owner quotes, SHAs, ids and paths exactly: never paraphrase, merge, translate or drop these
lines. End the notes with: "Before the next action, re-read the manager skill and every file in
its references/ whose trigger applies; never work from a summary of a file."
EOF
    ;;
  SessionStart)
    printf '%s %s %s %s%s\n' \
      'manager-plugin: this session was compacted during a manager run: before the next action,' \
      're-read the manager skill (invoke it again if its text is missing or cut short) and every' \
      'file in its references/ whose trigger applies now; never work from a summary of a file.' \
      '(That run has ended: ignore this line and remove ~/.claude/manager-runs/active/' "$id.)"
    ;;
esac
exit 0
