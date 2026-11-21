#!/usr/bin/env python3
"""context_watch: tells a manager run's orchestrator when its own context has grown large.

Usage:
  context_watch.py MARKERS < the hook input

The logic of `hooks/manager-context-watch.sh`, the plugin's PostToolUse hook on the Agent tool.
MARKERS is the folder of the run markers (`~/.claude/manager-runs/active`): one file per session
with a manager run in progress, named by the session id. When the hook input's session has one
and the last request in its transcript (the input's `transcript_path`; `usage.last` reads only
the file's end) held more tokens than the budget, one line of JSON is printed, the hook output
that adds one line to the session's context (`hookSpecificOutput.additionalContext`): write the
working-notes lines out now, and suggest `/compact` to the owner at the next stop.

The budget is 200,000 tokens; the environment variable `MANAGER_CONTEXT_BUDGET` (a whole number
above 0) sets another. It is no `.codemap.json` setting: an orchestrator has one context,
whichever repository the run works in.

Nothing is printed otherwise: no marker for the session, a subagent's own tool call (the input
carries an agent id), a context at or under the budget, no transcript or no request in its end,
an input that can't be read. Only the Python standard library is used (Python 3.8+); the marker
and the transcript are only read, nothing is written and nothing is sent anywhere. Exit status 0,
whatever happens.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # usage.py: beside this file
import usage  # noqa: E402

BUDGET = 200000
LINE = ("manager-plugin: this session's context is {size:,} tokens, over the manager run's "
        "budget of {budget:,}: write every working-notes line of the run out now, each as it "
        "stands (when this line comes again: only the ones that changed since), and when you "
        "next stop for the owner, suggest that they run `/compact` before they answer. (That "
        "run has ended: ignore this line and remove ~/.claude/manager-runs/active/{session}.)")


def budget():
    try:
        value = int(os.environ.get("MANAGER_CONTEXT_BUDGET", ""))
    except ValueError:
        return BUDGET
    return value if value > 0 else BUDGET


def line(data, markers):
    """The context line for a hook input, or None."""
    if not isinstance(data, dict) or data.get("agent_id"):
        return None
    session, path = data.get("session_id"), data.get("transcript_path")
    if not isinstance(session, str) or not usage.NAME.fullmatch(session) \
            or not isinstance(path, str) \
            or not os.path.isfile(os.path.join(markers, session)):
        return None
    size, limit = usage.last(path), budget()
    if size is None or size <= limit:
        return None
    return LINE.format(size=size, budget=limit, session=session)


def main(argv=None):
    try:
        markers = (sys.argv[1:] if argv is None else argv)[0]
        text = line(json.loads(sys.stdin.buffer.read()), markers)
        if text:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                     "additionalContext": text}}))
    except Exception:  # an advisory hook: it fails open
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
