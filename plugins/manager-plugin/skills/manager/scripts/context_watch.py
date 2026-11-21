#!/usr/bin/env python3
"""context_watch: tells a manager run's orchestrator once when its own context crosses the budget.

Usage:
  context_watch.py MARKERS < the hook input

The logic of `hooks/manager-context-watch.sh`, the plugin's PostToolUse hook on the Agent tool.
MARKERS is the folder of the run markers (`~/.claude/manager-runs/active`): one file per session
with a manager run in progress, named by the session id. When the hook input's session has one,
the last request in its transcript (the input's `transcript_path`; `usage.back` reads only the
file's end) held more tokens than the budget, and the request before it that called the Agent
or Task tool (this hook's previous chance to speak) held no more than the budget, one line of
JSON is printed, the hook output that adds one line to the session's context
(`hookSpecificOutput.additionalContext`): make sure the run's notes file
(`~/.claude/manager-runs/notes/<session id>.md`) is current, without printing the notes, and
suggest `/compact` to the owner once, at the next stop. So the line comes once per crossing, not
after every subagent return above the budget; a compaction brings the context under it again.
No earlier such request in the transcript's end → the line comes, as for a first crossing.
Stateless: nothing but the transcript records whether the line came before.

The budget is 200,000 tokens; the environment variable `MANAGER_CONTEXT_BUDGET` (a whole number
above 0) sets another. It is no `.codemap.json` setting: an orchestrator has one context,
whichever repository the run works in.

Nothing is printed otherwise: no marker for the session, a subagent's own tool call (the input
carries an agent id), a context at or under the budget, one already over it at the previous
Agent call, no transcript or no request in its end, an input that can't be read. Only the
Python standard library is used (Python 3.8+); the marker and the transcript are only read,
nothing is written and nothing is sent anywhere. Exit status 0, whatever happens.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # usage.py: beside this file
import usage  # noqa: E402

BUDGET = 200000
LINE = ("manager-plugin: this session's context is {size:,} tokens, over the manager run's "
        "budget of {budget:,}: make sure your notes file, ~/.claude/manager-runs/notes/"
        "{session}.md, is current (never print the notes), and when you next stop for the "
        "owner, suggest once that they run `/compact` before they answer. (If no manager run is "
        "in progress any more, ignore this line and remove ~/.claude/manager-runs/active/"
        "{session}.)")
SPAWN = ("Agent", "Task")  # the tools this hook follows (hooks.json: `Agent|Task`)


def budget():
    try:
        value = int(os.environ.get("MANAGER_CONTEXT_BUDGET", ""))
    except ValueError:
        return BUDGET
    return value if value > 0 else BUDGET


def spawns(record):
    """True for a request record whose content calls the Agent or Task tool."""
    content = record["message"].get("content")
    return isinstance(content, list) and any(
        isinstance(part, dict) and part.get("type") == "tool_use" and part.get("name") in SPAWN
        for part in content)


def sizes(path):
    """(the last request's context size, the one of the last request before it that called the
    Agent or Task tool, or None), or (None, None): no request in the transcript's end. A request
    has a record per content block, all with its message id; the last one read is complete."""
    current = key = None
    seen = {}  # message id -> its size, from its last record
    for record, size in usage.back(path):
        name = record["message"]["id"]
        if current is None:
            current, key = size, name
        if name == key:
            continue
        seen.setdefault(name, size)
        if spawns(record):
            return current, seen[name]
    return current, None


def line(data, markers):
    """The context line for a hook input, or None."""
    if not isinstance(data, dict) or data.get("agent_id"):
        return None
    session, path = data.get("session_id"), data.get("transcript_path")
    if not isinstance(session, str) or not usage.NAME.fullmatch(session) \
            or not isinstance(path, str) \
            or not os.path.isfile(os.path.join(markers, session)):
        return None
    (size, before), limit = sizes(path), budget()
    if size is None or size <= limit or (before is not None and before > limit):
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
