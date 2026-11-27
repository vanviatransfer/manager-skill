#!/usr/bin/env python3
"""usage: what a Claude Code session's orchestrator and its subagents spent, from the transcripts.

Usage:
  usage.py SESSION_ID [AGENT[=MODEL] ...] [--since WHEN] [--streaks] [--tools]

Prints one line for the session's main conversation (`orchestrator`) and one per subagent, oldest
first; with AGENT names (`orchestrator`, or a subagent's id as the Agent tool returns it) only
those, in that order. `AGENT=MODEL` names the model the agent should have run on (the model
strategy's, as dispatched: `sonnet`, a full model id; several: `a,b`; `inherit`: none, no
check): when a request it counts ran on a model matching none of them, its `model` field ends in
`!=MODEL`. Both sides are lower-cased and lose a context suffix (`[1m]`), a trailing `-YYYYMMDD`
or `@YYYYMMDD` date and a provider prefix (up to the last `.` or `/` before the first digit). A
name with a version digit must then equal the id or end it after a `-`; a name with no letters
never matches (it is marked); an alias (no digit: `sonnet`) need only be part of it. A suffix
after the version (`-v1:0`) is a mismatch: a false mark, never a false pass. When every name given
(`inherit` aside) is empty after that (`=`, `=,`, `=.`, `=[1m]`, `=-20260101`), the line is marked
`!=unknown`: the check is never turned off by a name that names nothing. With `--since WHEN` a
line counts only the records stamped at or after WHEN, a file's modification time (the manager's
run marker: the run, not the whole session) or an ISO 8601 time; the first request counted is
then no resume. Each line, with ` | ` between its fields:

  usage | agent | role | model | requests | input | cache read | cache write 5m | cache write 1h |
  output | context at return | warm resumes | cold resumes | seconds

- agent: `orchestrator` or the subagent's id; role: `main`, or the subagent's type from its
  `.meta.json`; model: the last request's (and `!=MODEL`, above).
- requests: API requests. A transcript holds one record per content block, each with its
  request's message id and usage, so a request is counted once, by message id.
- input, cache read, cache write 5m, cache write 1h, output: tokens, summed over the requests
  (input: the uncached part). A request without the split by lifetime counts as 5-minute writes,
  the API's default.
- context at return: the last request's input + cache write + cache read + output, the figure the
  Agent tool reports as `subagent_tokens`.
- warm resumes, cold resumes: requests sent 60 seconds or more after the agent's previous one
  ended. For a subagent, only those a prompt started (a message that resumed it): a request
  that a tool result started (a `user` record whose content holds a `tool_result`) is no
  resume, however long the tool call took. For the orchestrator those count too (a wait for a
  subagent, a long tool call), beside the owner's prompts. A record is stamped when its content
  block ends, so a request counts as sent at the prompt or tool result that started it (the
  last `user` record before its first record), and its own time, thinking included, is no gap.
  Cold: it read less than half of the previous request's prompt from the cache, so the cache
  had expired and the context was written again; warm otherwise. The first request after a
  compaction (a `compact_boundary` record between the two) is not counted.
- seconds: from the transcript's first record to its last (a reviewer's: how long the review
  took; a resumed agent's includes the waits between its rounds).

With `--streaks`, each `usage` line is followed by one more (off by default):

  streaks | agent | failure streaks | longest | tool

- failure streaks: the runs of 3 or more consecutive tool calls with the same tool and the same
  input, each ending in an error (its tool result has `is_error`); a call without a result ends
  a run. longest: the calls in the longest run; tool: its tool's name (never the input), `none`
  without a run; `unknown` for a transcript that can't be read. `--since` bounds them too.

With `--tools`, each agent's lines (`usage`, then `streaks` if asked) are followed by where its
context went (off by default):

  tools | agent | tool | calls | result chars | errors
  reads | agent | Read calls | distinct files | re-reads unchanged
  map | agent | map queries | other map calls | searches

- tools: one line per tool the agent called, the most result characters first (then the most
  calls, then by name); none for an agent that called none. result chars: the characters of the
  tool results returned to the model (a text result's length, or its text parts' summed; an
  image or any other part counts 0), exact, no token estimate; errors: the results with
  `is_error`. A call without a result counts as a call only; a result whose call is not counted
  (before `--since`) is not counted.
- reads: the Read calls, the distinct paths they read, and the re-reads unchanged: a Read of a
  path with the same offset and limit as an earlier Read by this agent that did not fail, with no
  Edit, MultiEdit, Write or NotebookEdit call (failed or not) of that path by this agent between
  them. A Read of another range of the file is no re-read. Changes made by another agent, by a
  Bash command or outside the transcript are not seen, so such a Read counts as a re-read.
- map: map queries, Bash calls whose command runs `codemap.py` with the action `query` or
  `mentions` (the first action word after `codemap.py`); other map calls, those with another
  action or none found; searches, Grep and Glob calls and Bash calls whose first command is
  `grep`, `rg`, `find` or `git grep`. The first command is the first word after any leading
  `cd ... &&`, variable assignments (`A=b`) and `timeout [options] N`; a search later in a
  pipeline or after another command is not seen.

The tool names are printed, never their inputs, paths or commands; `unknown` (one `tools` line)
for a transcript that can't be read. `--since` bounds them too.

A value that can't be read is `unknown`: every value of a missing transcript, the role without a
`.meta.json`, the resumes and seconds of a transcript without timestamps.

The transcripts are `projects/<project>/<SESSION_ID>.jsonl` and, beside it,
`<SESSION_ID>/subagents/agent-<id>.jsonl` under the Claude config folder (`CLAUDE_CONFIG_DIR`, else
`~/.claude`). A session that moved between working folders has them under several project
folders: all are read as one. The format is undocumented: a line or a field that can't be read is
skipped, and only the requests a transcript records are counted.

Only the Python standard library is used (Python 3.8+). The files are only read; nothing is
written but the lines on standard output, and nothing is sent anywhere. Exit status 0, whatever
is missing (2 for a command line without a session id, or with a `--since` that is neither).
"""
import argparse
import bisect
import datetime
import glob
import json
import os
import re
import shlex
import sys

COLUMNS = ("agent", "role", "model", "requests", "input", "cache read", "cache write 5m",
           "cache write 1h", "output", "context at return", "warm resumes", "cold resumes",
           "seconds")
FIELDS = ("model", "requests", "input", "read", "write_5m", "write_1h", "output", "context",
          "warm", "cold", "seconds")
GAP = 60  # seconds after the previous request's end from which the next one counts as a resume
PROMPT = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
TAIL = 1 << 20  # the bytes of a transcript's end that `back` and `last` read
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


def request(record):
    """(message id, usage, model) of a record that belongs to an API request, else None."""
    message = record.get("message") if record.get("type") == "assistant" else None
    if not isinstance(message, dict):
        return None
    key, usage, model = (message.get(k) for k in ("id", "usage", "model"))
    if not isinstance(key, str) or not isinstance(usage, dict) \
            or model == "<synthetic>":  # an error message, not a request
        return None
    return key, usage, model


def answer(record):
    """True for a `user` record that carries a tool result, not a prompt."""
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return isinstance(content, list) and any(
        isinstance(part, dict) and part.get("type") == "tool_result" for part in content)


def read(paths, since=None, waits=True):
    """The totals of one conversation's transcript files: a dict with the keys of FIELDS and
    `start`, the time of the first record (None: unknown), or None when no file can be read.
    With `since`, a time in seconds, only the records stamped at or after it count. Without
    `waits`, a request that a tool result started is no resume."""
    requests = {}  # message id -> [time of its first record, of its last, model, usage]
    models = set()  # every model a counted request ran on
    sent = []  # (time, whether a tool result) of the prompts and tool results
    compacted = []  # the times of the compactions
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
                    if since is not None and (at is None or at < since):
                        continue
                    if at is not None:
                        start = at if start is None else min(start, at)
                        end = at if end is None else max(end, at)
                    kind = record.get("type")
                    if at is not None and kind == "user":
                        sent.append((at, answer(record)))
                    elif at is not None and kind == "system" \
                            and record.get("subtype") == "compact_boundary":
                        compacted.append(at)
                    found = request(record)
                    if not found:
                        continue
                    key, usage, model = found
                    entry = requests.setdefault(key, [at, at, None, None])
                    if at is not None:
                        entry[0] = at if entry[0] is None else min(entry[0], at)
                        entry[1] = at if entry[1] is None else max(entry[1], at)
                    entry[2:] = model, usage  # the last record's: the complete one
                    if isinstance(model, str):
                        models.add(model)
        except OSError:
            continue
    if not opened:
        return None
    timed = start is not None
    total = dict.fromkeys(FIELDS, 0)
    total.update(model=None, context=None, start=start, models=models,
                 seconds=int(end - start) if timed else None,
                 warm=0 if timed else None, cold=0 if timed else None)
    sent.sort()
    before = None  # the previous request: (time of its last record, its prompt's size)
    for first, ended, model, usage in sorted(requests.values(),
                                             key=lambda r: (r[0] is None, r[0] or 0)):
        fresh, cached, written = (count(usage, key) for key in PROMPT)
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
        if before and None not in (first, before[0]):
            asked = bisect.bisect_right(sent, (first, True))  # what started it: the last before
            if asked and sent[asked - 1][0] - before[0] >= GAP \
                    and (waits or not sent[asked - 1][1]) \
                    and not any(before[0] < at <= first for at in compacted):
                total["cold" if cached * 2 < before[1] else "warm"] += 1
        before = (ended, prompt)
    return total


def back(path, tail=TAIL, compaction=False):
    """The request records in a transcript's last `tail` bytes, from the last back: (record,
    context size) for each, the size counted as `context at return` counts it. With
    `compaction`, none from before the last `compact_boundary` record. Only that end of the file
    is read, so a long transcript costs no more than a short one; no file that can be read →
    nothing."""
    try:
        with open(path, "rb") as fh:
            cut = max(0, fh.seek(0, os.SEEK_END) - tail - 1)  # with the byte before them
            fh.seek(cut)
            lines = fh.read().split(b"\n")
    except (OSError, ValueError):
        return
    for line in reversed(lines[1:] if cut else lines):  # after a cut, the first is a part
        bound = compaction and b"compact_boundary" in line
        if b'"usage"' not in line and not bound:
            continue
        try:
            record = json.loads(line.decode("utf-8", "replace"))
        except (ValueError, RecursionError):
            continue
        if bound and isinstance(record, dict) and record.get("type") == "system" \
                and record.get("subtype") == "compact_boundary":
            return
        found = request(record) if isinstance(record, dict) else None
        if found:
            yield record, sum(count(found[1], key) for key in PROMPT + ("output_tokens",))


STREAK = 3  # identical failing tool calls in a row from which they count as a failure streak


def blocks(record, kind):
    """The content blocks of type `kind` in a record's message."""
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [part for part in content if isinstance(part, dict) and part.get("type") == kind] \
        if isinstance(content, list) else []


def streaks(paths, since=None):
    """(the failure streaks, the calls in the longest, its tool's name) of one conversation's
    transcript files, or None when no file can be read (see `--streaks`)."""
    calls, failed, opened = [], set(), False  # calls: (id, tool, its input as JSON), in order
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
                    if since is not None and (when(record) or -1) < since:
                        continue
                    for use in blocks(record, "tool_use"):
                        try:
                            calls.append((use.get("id"), use.get("name"),
                                          json.dumps(use.get("input"), sort_keys=True)))
                        except (TypeError, ValueError, RecursionError):
                            calls.append((use.get("id"), use.get("name"), None))
                    for done in blocks(record, "tool_result"):
                        if done.get("is_error") is True and isinstance(done.get("tool_use_id"),
                                                                       str):
                            failed.add(done["tool_use_id"])
        except OSError:
            continue
    if not opened:
        return None
    seen, found, longest, tool = set(), 0, 0, None
    run, before = 0, None
    for key, name, given in calls + [(None, None, None)]:  # the last one ends the last run
        if key in seen:
            continue  # the same call in two files (a session that moved) counts once
        if key is not None:
            seen.add(key)
        same = key in failed and given is not None and (name, given) == before
        if not same:
            if run >= STREAK:
                found += 1
                if run > longest:
                    longest, tool = run, before[0]
            run = 1 if key in failed and given is not None else 0
        else:
            run += 1
        before = (name, given) if run else None
    return found, longest, tool


def streak_line(agent, found):
    values = ["unknown"] * 3 if found is None else [str(found[0]), str(found[1]),
                                                     tag(found[2]) if found[2] else "none"]
    return " | ".join(["streaks", tag(agent)] + values)


EDITS = ("Edit", "MultiEdit", "Write", "NotebookEdit")  # the tools that change a file
SEARCHES = ("grep", "rg", "find")  # a Bash command that starts with one is a search
ACTIONS = ("build", "check", "query", "mentions", "changed", "impact", "detect", "install-hook",
           "uninstall-hook", "pre-commit", "claude-hook", "rules-hint", "session-hook")
ASSIGNED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def size(content):
    """The characters of a tool result's content: a text, or its text parts' summed."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(part["text"]) for part in content if isinstance(part, dict)
                   and part.get("type") == "text" and isinstance(part.get("text"), str))
    return 0


def words(command):
    try:
        return shlex.split(command)
    except ValueError:  # an unclosed quote
        return command.split()


def first(command):
    """The first command's words, without a leading `cd ... &&`, assignments and `timeout`."""
    found = words(command)
    while found:
        if found[0] == "cd" and "&&" in found:
            found = found[found.index("&&") + 1:]
        elif ASSIGNED.match(found[0]):
            found = found[1:]
        elif found[0] == "timeout":
            found = found[1:]
            while found and found[0].startswith("-"):
                found = found[1:]
            found = found[1:]  # the duration
        else:
            break
    return found


def search(command):
    found = first(command)
    name = os.path.basename(found[0]) if found else ""
    return name in SEARCHES or (name == "git" and found[1:2] == ["grep"])


def mapped(command):
    """None for a command that does not run `codemap.py`, else whether it runs a query."""
    found = words(command)
    for at, word in enumerate(found):
        if os.path.basename(word) == "codemap.py":
            action = next((w for w in found[at + 1:] if w in ACTIONS), None)
            return action in ("query", "mentions")
    return None


def tools(paths, since=None):
    """({tool: [calls, result chars, errors]}, (Read calls, distinct files, re-reads
    unchanged), (map queries, other map calls, searches)) of one conversation's transcript
    files, or None when no file can be read (see `--tools`)."""
    calls, results, opened = {}, {}, False  # id -> (tool, input); id -> (chars, error)
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
                    if since is not None and (when(record) or -1) < since:
                        continue
                    for use in blocks(record, "tool_use"):
                        key = use.get("id")
                        key = key if isinstance(key, str) else object()  # no id: its own call
                        given = use.get("input")
                        calls.setdefault(key, (use.get("name"),
                                               given if isinstance(given, dict) else {}))
                    for done in blocks(record, "tool_result"):
                        key = done.get("tool_use_id")
                        if isinstance(key, str):  # the same result in two files counts once
                            results.setdefault(key, (size(done.get("content")),
                                                     done.get("is_error") is True))
        except OSError:
            continue
    if not opened:
        return None
    by_tool = {}
    reads, files, again, read = 0, set(), 0, set()  # read: (path, offset, limit) since a change
    queries = others = searches = 0
    for key, (name, given) in calls.items():  # in the order the calls were made
        entry = by_tool.setdefault(tag(name), [0, 0, 0])
        chars, error = results.get(key, (0, False))
        entry[0] += 1
        entry[1] += chars
        entry[2] += error
        target = given.get("notebook_path" if name == "NotebookEdit" else "file_path")
        if name == "Read":
            reads += 1
            if isinstance(target, str):
                files.add(target)
                span = (target, repr(given.get("offset")), repr(given.get("limit")))
                again += span in read
                if not error:
                    read.add(span)
        elif name in EDITS and isinstance(target, str):
            read = {span for span in read if span[0] != target}
        elif name in ("Grep", "Glob"):
            searches += 1
        command = given.get("command")
        if name == "Bash" and isinstance(command, str):
            query = mapped(command)
            queries += query is True
            others += query is False
            searches += search(command)
    return by_tool, (reads, len(files), again), (queries, others, searches)


def tool_lines(agent, found):
    if found is None:
        return [" | ".join(["tools", tag(agent)] + ["unknown"] * 4),
                " | ".join(["reads", tag(agent)] + ["unknown"] * 3),
                " | ".join(["map", tag(agent)] + ["unknown"] * 3)]
    by_tool, reads, maps = found
    order = sorted(by_tool.items(), key=lambda item: (-item[1][1], -item[1][0], item[0]))
    return [" | ".join(["tools", tag(agent), name] + [str(int(v)) for v in values])
            for name, values in order] \
        + [" | ".join(["reads", tag(agent)] + [str(v) for v in reads]),
           " | ".join(["map", tag(agent)] + [str(v) for v in maps])]


def last(path, tail=TAIL):
    """The context size at the last request in a transcript's last `tail` bytes (the figure
    `context at return` gives), or None: no request there, or no file that can be read (`back`
    reads the records)."""
    for _, size in back(path, tail):
        return size
    return None


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


def paths(session, agent):
    """The transcript files of a session's agent (`orchestrator` or a subagent's id)."""
    transcripts, folders = find(session)
    if agent == "orchestrator":
        return transcripts
    return [os.path.join(folder, "agent-%s.jsonl" % agent) for folder in folders] \
        if NAME.fullmatch(agent) else []


def rows(session, agents=(), since=None):
    """[(agent, role, totals or None)]: the named agents in that order, else the orchestrator and
    then every subagent of the session, oldest first; `since` as in `read`."""
    transcripts, folders = find(session)
    names = list(dict.fromkeys(agents))
    if not names:
        files = [os.path.basename(path) for folder in folders
                 for path in glob.glob(os.path.join(glob.escape(folder), "agent-*.jsonl"))]
        names = ["orchestrator"] + sorted({name[len("agent-"):-len(".jsonl")] for name in files})
    found = []
    for name in names:
        if name == "orchestrator":
            found.append((name, "main", read(transcripts, since)))
        elif NAME.fullmatch(name):
            found.append((name, role(folders, name), read(
                (os.path.join(folder, "agent-%s.jsonl" % name) for folder in folders), since,
                waits=False)))
        else:
            found.append((name, None, None))
    if not agents:
        found[1:] = sorted(found[1:], key=age)
    return found


def age(row):
    start = row[2]["start"] if row[2] else None
    return start is None, start or 0, row[0]


DATED = re.compile(r"[-@]\d{8}$")  # a full model id's date: `vendor-x-1-20250101`


def family(model):
    """A model id or name in lower case, without a context suffix (`[1m]`), a trailing date or
    a provider prefix (up to the last `.` or `/` before the first digit, so `4.6` stays)."""
    name = DATED.sub("", model.split("[")[0].strip().lower())
    head = re.split(r"\d", name, maxsplit=1)[0]
    return name[max(head.rfind("."), head.rfind("/")) + 1:]


def matches(name, model):
    """A name with a version digit must equal the id or end it after a `-`; an alias need only
    be in it. Anything after the version (`-v1:0`) is a mismatch: a false mark, never a pass."""
    model = family(model)
    if not any(c.isalpha() for c in name):
        return False  # a bare version (`4-6`, `4.6`) names no family: marked, never a pass
    if any(c.isdigit() for c in name):
        return model == name or model.endswith("-" + name)
    return name in model


def off(totals, expected):
    """True when a request in `totals` ran on a model that matches none of `expected` (both as
    `family` gives them: `big` and `vendor-big-4-6[1m]` match `prov.vendor-big-4-6@20260101`;
    `big-4` does not match `vendor-big-4-6`)."""
    return bool(expected and totals) and any(
        not any(matches(name, model) for name in expected) for model in totals["models"])


def render(agent, kind, totals, expected=()):
    values = [totals[key] if totals else None for key in FIELDS]
    model = tag(values[0]) + ("!=" + ",".join(map(tag, expected)) if off(totals, expected) else "")
    return " | ".join(["usage", tag(agent), tag(kind), model]
                      + ["unknown" if value is None else str(value) for value in values[1:]])


def expect(arg):
    """`AGENT[=MODEL[,MODEL...]]`: (AGENT, the models as `family` gives them). `inherit` (the
    session's model, whatever it is) expects nothing, and makes the agent's line unmarked. With
    `=` but every name empty after `family` (`a1=`, `a1=,`, `a1=[1m]`), it expects `("",)`, which
    matches no model: the line is marked, never silently unchecked."""
    name, sep, models = arg.partition("=")
    names = tuple(family(m) for m in models.split(","))
    if "inherit" in names or not sep:
        return name, ()
    return name, tuple(m for m in names if m) or ("",)


def moment(text):
    """`--since`: a file's modification time, else an ISO 8601 time, in seconds."""
    try:
        return os.path.getmtime(text)
    except (OSError, ValueError):
        at = when({"timestamp": text})
    if at is None:
        raise argparse.ArgumentTypeError("%r is neither a file nor an ISO 8601 time" % text)
    return at


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="usage.py", description="What a session's orchestrator and subagents spent: one "
                                     "`usage` line each (" + " | ".join(COLUMNS) + ").")
    ap.add_argument("session", metavar="SESSION_ID")
    ap.add_argument("agents", metavar="AGENT", nargs="*", type=expect,
                    help="`orchestrator` or a subagent's id, with =MODEL the model it should "
                         "have run on (mismatch: `model` ends in !=MODEL); none: all of them")
    ap.add_argument("--since", metavar="WHEN", type=moment,
                    help="count only the records stamped at or after WHEN: a file's "
                         "modification time (the run marker's: the run) or an ISO 8601 time")
    ap.add_argument("--streaks", action="store_true",
                    help="after each line, one `streaks` line: runs of 3 or more identical tool "
                         "calls in a row that each ended in an error, and the longest")
    ap.add_argument("--tools", action="store_true",
                    help="after each agent's lines, its `tools` lines (calls, result characters "
                         "and errors by tool), a `reads` line and a `map` line")
    args = ap.parse_intermixed_args(argv)
    expected = dict(args.agents)  # the last =MODEL given for an agent
    for row in rows(args.session, [name for name, _ in args.agents], args.since):
        print(render(*row, expected=expected.get(row[0], ())))
        if args.streaks:
            print(streak_line(row[0], streaks(paths(args.session, row[0]), args.since)))
        if args.tools:
            for line in tool_lines(row[0], tools(paths(args.session, row[0]), args.since)):
                print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
