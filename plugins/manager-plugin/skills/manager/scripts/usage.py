#!/usr/bin/env python3
"""usage: what a Claude Code session's orchestrator and its subagents spent, from the transcripts.

Usage:
  usage.py SESSION_ID [AGENT ...]

Prints one line for the session's main conversation (`orchestrator`) and one per subagent, oldest
first; with AGENT names (`orchestrator`, or a subagent's id as the Agent tool returns it) only
those, in that order. Each line, with ` | ` between its fields:

  usage | agent | role | model | requests | input | cache read | cache write 5m | cache write 1h |
  output | context at return | warm resumes | cold resumes | seconds

- agent: `orchestrator` or the subagent's id; role: `main`, or the subagent's type from its
  `.meta.json`; model: the last request's.
- requests: API requests. A transcript holds one record per content block, each with its
  request's message id and usage, so a request is counted once, by message id.
- input, cache read, cache write 5m, cache write 1h, output: tokens, summed over the requests
  (input: the uncached part). A request without the split by lifetime counts as 5-minute writes,
  the API's default.
- context at return: the last request's input + cache write + cache read + output, the figure the
  Agent tool reports as `subagent_tokens`.
- warm resumes, cold resumes: requests that came 60 seconds or more after the agent's previous
  one (a resume, a wait for a subagent or the owner, a long tool call). Cold: it read less than
  half of the previous request's prompt from the cache, so the cache had expired and the context
  was written again; warm otherwise. A request whose prompt is smaller than the previous one
  follows a compaction and is not counted.
- seconds: from the transcript's first record to its last (a reviewer's: how long the review
  took; a resumed agent's includes the waits between its rounds).

A value that can't be read is `unknown`: every value of a missing transcript, the role without a
`.meta.json`, the resumes and seconds of a transcript without timestamps.

The transcripts are `projects/<project>/<SESSION_ID>.jsonl` and, beside it,
`<SESSION_ID>/subagents/agent-<id>.jsonl` under the Claude config folder (`CLAUDE_CONFIG_DIR`, else
`~/.claude`). A session that moved between working folders has them under several project
folders: all are read as one. The format is undocumented: a line or a field that can't be read is
skipped, and only the requests a transcript records are counted.

Only the Python standard library is used (Python 3.8+). The files are only read; nothing is
written but the lines on standard output, and nothing is sent anywhere. Exit status 0, whatever
is missing (2 for a command line without a session id).
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

COLUMNS = ("agent", "role", "model", "requests", "input", "cache read", "cache write 5m",
           "cache write 1h", "output", "context at return", "warm resumes", "cold resumes",
           "seconds")
FIELDS = ("model", "requests", "input", "read", "write_5m", "write_1h", "output", "context",
          "warm", "cold", "seconds")
GAP = 60  # seconds after the previous request from which the next one counts as a resume
NAME = re.compile(r"[A-Za-z0-9_-]+")  # a session id, an agent id: never a path or a pattern


def when(record):
    """A record's time in seconds, or None."""
    try:
        text = record["timestamp"].replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(text).timestamp()
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError, OSError):
        return None


def count(usage, key):
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def read(paths):
    """The totals of one conversation's transcript files: a dict with the keys of FIELDS and
    `start`, the time of the first record (None: unknown), or None when no file can be read."""
    requests = {}  # message id -> [time of its first record, of its last, model, usage]
    start = end = None
    opened = False
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                opened = True
                for line in fh:
                    try:
                        record = json.loads(line)
                    except (ValueError, RecursionError):
                        continue
                    if not isinstance(record, dict):
                        continue
                    at = when(record)
                    if at is not None:
                        start = at if start is None else min(start, at)
                        end = at if end is None else max(end, at)
                    message = record.get("message")
                    if record.get("type") != "assistant" or not isinstance(message, dict):
                        continue
                    key, usage, model = (message.get(k) for k in ("id", "usage", "model"))
                    if not isinstance(key, str) or not isinstance(usage, dict) \
                            or model == "<synthetic>":  # an error message, not a request
                        continue
                    request = requests.setdefault(key, [at, at, None, None])
                    if at is not None:
                        request[0] = at if request[0] is None else min(request[0], at)
                        request[1] = at if request[1] is None else max(request[1], at)
                    request[2:] = model, usage  # the last record's: the complete one
        except OSError:
            continue
    if not opened:
        return None
    timed = start is not None
    total = dict.fromkeys(FIELDS, 0)
    total.update(model=None, context=None, start=start,
                 seconds=int(end - start) if timed else None,
                 warm=0 if timed else None, cold=0 if timed else None)
    before = None  # the previous request: (time of its last record, its prompt's size)
    for first, last, model, usage in sorted(requests.values(),
                                            key=lambda r: (r[0] is None, r[0] or 0)):
        fresh, cached, written = (count(usage, key) for key in (
            "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        hour = min(written, count(usage.get("cache_creation"), "ephemeral_1h_input_tokens"))
        output = count(usage, "output_tokens")
        prompt = fresh + cached + written
        total["requests"] += 1
        total["input"] += fresh
        total["read"] += cached
        total["write_5m"] += written - hour
        total["write_1h"] += hour
        total["output"] += output
        total["context"] = prompt + output
        total["model"] = model
        if before and None not in (first, before[0]) and first - before[0] >= GAP \
                and prompt >= before[1]:
            total["cold" if cached * 2 < before[1] else "warm"] += 1
        before = (last, prompt)
    return total


def tag(value):
    """A value as one word that is safe in a ` | `-separated line."""
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value) if isinstance(value, str) else ""
    return text or "unknown"


def role(folders, agent):
    for folder in folders:
        try:
            with open(os.path.join(folder, "agent-%s.meta.json" % agent),
                      encoding="utf-8") as fh:
                return json.load(fh)["agentType"]
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            continue
    return None


def find(session):
    """(the session's transcripts, its subagents folders), one of each per project folder."""
    if not NAME.fullmatch(session):
        return [], []
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"),
                                                                 ".claude")
    base = os.path.join(glob.escape(config), "projects", "*", session)
    return sorted(glob.glob(base + ".jsonl")), sorted(glob.glob(os.path.join(base, "subagents")))


def rows(session, agents=()):
    """[(agent, role, totals or None)]: the named agents in that order, else the orchestrator and
    then every subagent of the session, oldest first."""
    transcripts, folders = find(session)
    names = list(dict.fromkeys(agents))
    if not names:
        files = [os.path.basename(path) for folder in folders
                 for path in glob.glob(os.path.join(glob.escape(folder), "agent-*.jsonl"))]
        names = ["orchestrator"] + sorted({name[len("agent-"):-len(".jsonl")] for name in files})
    found = []
    for name in names:
        if name == "orchestrator":
            found.append((name, "main", read(transcripts)))
        elif NAME.fullmatch(name):
            found.append((name, role(folders, name), read(
                os.path.join(folder, "agent-%s.jsonl" % name) for folder in folders)))
        else:
            found.append((name, None, None))
    if not agents:
        found[1:] = sorted(found[1:], key=age)
    return found


def age(row):
    start = row[2]["start"] if row[2] else None
    return start is None, start or 0, row[0]


def render(agent, kind, totals):
    values = [totals[key] if totals else None for key in FIELDS]
    return " | ".join(["usage", tag(agent), tag(kind), tag(values[0])]
                      + ["unknown" if value is None else str(value) for value in values[1:]])


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="usage.py", description="What a session's orchestrator and subagents spent: one "
                                     "`usage` line each (" + " | ".join(COLUMNS) + ").")
    ap.add_argument("session", metavar="SESSION_ID")
    ap.add_argument("agents", metavar="AGENT", nargs="*",
                    help="`orchestrator` or a subagent's id; none: all of them")
    args = ap.parse_args(argv)
    for row in rows(args.session, args.agents):
        print(render(*row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
