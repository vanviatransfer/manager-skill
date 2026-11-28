#!/usr/bin/env python3
"""usage: what a Claude Code session's orchestrator and its subagents spent, from the transcripts.

Usage:
  usage.py SESSION_ID [AGENT[=MODEL] ...] [--since WHEN] [--streaks] [--tools] [--prefix]
          [--after-green]

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

Since plugin 0.9.24 each `streaks` line is followed by an `errors` line:

  errors | agent | errors | distinct signatures | repeated errors | requests after first repeat

- errors: the tool results with `is_error` (of calls counted). A signature is the tool's name
  and the result's first line with quoted strings, paths, hex ids (6 or more hex digits, with a
  digit and a letter) and digits replaced by a placeholder; signatures are never printed.
  repeated errors: those whose signature an earlier error of this agent had (consecutive or
  not); requests after first repeat: the agent's requests after the first one's result (0
  without a repeat).

With `--tools`, each agent's lines (`usage`, then `streaks` if asked) are followed by where its
context went (off by default):

  tools | agent | tool | calls | result chars | errors | carried chars
  reads | agent | Read calls | distinct files | re-reads unchanged | bash reads | bash read chars
  map | agent | map queries | other map calls | searches

(`carried chars`, `bash reads` and `bash read chars` are new in plugin 0.9.24, which also
changed the order of the `tools` lines; the lines had no consumer.)

- tools: one line per tool the agent called, the most carried characters first (then the most
  result characters, the most calls, by name); none for an agent that called none. result
  chars: the characters of the tool results returned to the model (a text result's length, or
  its text parts' summed; an image or any other part counts 0), exact, no token estimate;
  errors: the results with `is_error`. A call without a result counts as a call only; a result
  whose call is not counted (before `--since`) is not counted. carried chars: each result's
  characters times the agent's later requests that still carried it: every request after it,
  up to the first compaction (a `compact_boundary` record) after it that does not list its
  record's uuid as preserved (`compactMetadata.preservedMessages`); a `compact_boundary`
  without `preservedMessages` counts as dropping everything, so for that span the figure is a
  lower bound. Context dropped any other way (old tool results cleared without such a record, a
  compaction not recorded) is not seen: the result counts as carried to the agent's end, so the
  figure is an upper bound there. Characters
  re-read from the cache cost less than new ones; this counts characters, not price.
- reads: the Read calls, the distinct paths they read, and the re-reads unchanged: a Read of a
  path with the same offset and limit as an earlier Read by this agent that did not fail, with no
  Edit, MultiEdit, Write or NotebookEdit call (failed or not) of that path by this agent between
  them. A Read of another range of the file is no re-read. Changes made by another agent, by a
  Bash command or outside the transcript are not seen, so such a Read counts as a re-read.
- map: map queries, Bash calls whose command runs `codemap.py` with the action `query` or
  `mentions` (the first action word after `codemap.py`); other map calls, those with another
  action or none found; searches, Grep and Glob calls and Bash calls whose first command is
  `grep`, `rg`, `find` or `git grep`. The first command is the first word after any leading
  `cd ... &&`, variable assignments (`A=b`, `A=b;`) and `timeout [options] N` (with an option's
  value word: `-s KILL`, `-k 5`, `--signal KILL`, `--kill-after 5`); a search later in a
  pipeline or after another command is not seen.
- bash reads: Bash calls whose first command (found as for searches) is `cat`, `head`,
  `tail`, `nl`, `less`, `more` or `bat`, or `sed` with `-n` (also in `-ne`, or
  `--quiet`/`--silent`) and without `-i` (`sed -ni`, `sed -n -i` edit), and that do not redirect
  its output to a file (`cat > f`, `cat f>out`, `cat f 1> out`, `&> f` write; `2>/dev/null` and
  `1>&2` do not), nor read a here-document (`cat <<EOF`); bash read chars: their results'
  characters. Only the first command is judged: it ends at an unquoted `;`, `|`, `&`, `&&`,
  `||` or newline, and a quoted `>` is text. A read later in a pipeline or after another command
  is not seen.

The tool names are printed, never their inputs, paths or commands; `unknown` (one `tools` line)
for a transcript that can't be read. `--since` bounds them too.

With `--prefix`, each agent's lines end with (off by default):

  prefix | agent | first request input tokens | total input tokens | share %

- input tokens: a request's input + cache read + cache writes. The first request counted
  approximates the fixed prefix (system prompt, tool schemas, the brief), which every later
  request sends again; it also holds the first prompt's own text, so it is an upper bound of
  the prefix. share: the most of the input the fixed prefix can account for, as it is sent
  again with every request: min(100, first x requests / total), one decimal. An upper bound:
  the first request also holds the first prompt, and compaction (a later request may send less)
  and the cache (a re-sent prefix is mostly a cheaper cache read) are ignored. `none` for an
  agent without a request. (Plugin 0.9.28 changed share from first / total, which understated
  the prefix; the line is opt-in and had no consumer.)

With `--after-green`, after them (off by default):

  after green | agent | green at request k of n | requests after | tool calls after |
  output tokens after | input tokens after

- What an agent spent after its last change already passed validation. The last change: the
  last Edit, MultiEdit, Write or NotebookEdit call, or Bash call that changes a file (below),
  whose result is no error. Green: the first later Bash call (or that Bash call itself when a
  simple command after its last change runs the test: `sed -i ... && pytest`, not `pytest &&
  sed -i ...`; a test run is not its last change, whether it writes its output to a file or
  the whole-text Python rule below takes it for one; since plugin 0.9.29) that ran a test or
  validation command and did not error: its command has the word `unittest`, `pytest` or
  `ctest` (not before a `.`: `pytest.ini`), or `npm test`, `npm run test`, `yarn test`, `pnpm
  test`, `go test`, `cargo test`, `mvn test`, `gradle test`, `make test` or `make check`; or
  it redirects output to a `.log` file and later runs `echo $?`, and then its result's last
  non-blank line must be `0` (the call itself does not fail). A command that hides a failure
  otherwise (`| tail`) counts as passed.
- k: the requests up to the one that made that call, of the agent's n; after: the requests,
  tool calls and tokens (input as for `--prefix`) after the call, the request that read its
  result included. `none` when there is no change or no green call after the last one.
- A Bash change (since plugin 0.9.28; before, Bash edits were not seen): the command, split
  into simple commands at unquoted `;`, `|`, `&`, `&&`, `||`, parentheses and newlines (quotes
  respected; here-document bodies are skipped), has one that runs `sed` or `gsed` with `-i`
  (`-ni`, `-i.bak`) or `--in-place`, or `perl` with `-i` in an option cluster before its
  script (`-pi`, `-i.bak`; not a letter of a `-M`, `-I` or `-e` argument: `perl -Mstrict -ne`
  is no change); writes standard output to a file (`>`, `>>`, `>|`, `&>`, `1>`, `>&f`, also a
  leading `> f.py` or `exec > f.py`; `2>` and `>&2` do not), or `tee` (`-a`) into one, the
  target written; runs `python`, `python3`, `python3.N` or `py` while the whole command
  text (a `-c` string or a here-document body included) has `open(` with a `w`, `a`, `x` or
  `r+` mode string, `write_text(` or `write_bytes(`; runs `git apply` (not `--check`, `--stat`)
  or `patch` (not `--dry-run`); or runs `mv` or `cp` with two or more operands onto a target
  (the last operand, or `-t`'s value). A target counts unless it is under `/dev/`, ends in
  `.log` or `.out`, or is under a temp folder (`/tmp`, `/var/tmp`, `$TMPDIR`, `$TMP`,
  `${TMPDIR:-...}`, `%TEMP%`, `%TMP%`, `C:\\Temp\\`, `...\\AppData\\Local\\Temp\\`,
  any case): a heredoc into a source file (`cat > a.py <<EOF`) is a change, one into `/tmp/x`
  is not. A `$VAR` or `${VAR}` in a target is first replaced by the value an earlier simple
  command of the same call assigned it (`S=/tmp/x; cat > "$S/a.py"`, `export S=...`). The
  command words are judged after leading assignments, `timeout`, `env`, `sudo` (and the value
  of its `-u`, `-g`, `-C` ... options), `nohup`, `command`, `exec` and `xargs` (and their
  option words). `git commit`, `git add`, `git push`, `git rebase` and any other command are no
  change. A heuristic: it over-counts (a Python write of a report file, the whole command
  text judged; a copy into the repository of what is not a source; a target still holding a
  `$VAR` not assigned in the call, `$(mktemp -d)` too, judged as written) and under-counts (a
  script file that writes, `bash -c '...'`, `find -exec sed -i`, `git checkout`, `git
  restore`, `rm`).

The order after each `usage` line: `streaks`, `errors`, the `tools` lines, `reads`, `map`,
`prefix`, `after green`, each only with its flag. `--since` bounds them all; each is
`unknown` for a transcript that can't be read.

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
                        key = use.get("id")
                        key = key if isinstance(key, str) else object()  # no id: its own call
                        try:
                            calls.append((key, use.get("name"),
                                          json.dumps(use.get("input"), sort_keys=True)))
                        except (TypeError, ValueError, RecursionError):
                            calls.append((key, use.get("name"), None))
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
ACTIONS = ("build", "check", "query", "mentions", "changed", "impact", "calls", "detect",
           "install-hook", "uninstall-hook", "pre-commit", "claude-hook", "rules-hint",
           "session-hook")
ASSIGNED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
TIMEOUT_VALUED = ("-s", "-k", "--signal", "--kill-after")  # `timeout` options with a value word


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


def first(command, found=None):
    """The first command's words, without a leading `cd ... &&`, assignments and `timeout`
    (`found`: the command's words already split)."""
    found = words(command) if found is None else found
    while found:
        if found[0] == "cd" and "&&" in found:
            found = found[found.index("&&") + 1:]
        elif ASSIGNED.match(found[0]):
            found = found[1:]
            if found and found[0] in (";", "&&", "\n"):  # `S=x; cat f`: cat is the first
                found = found[1:]
        elif found[0] == "timeout":
            found = found[1:]
            while found and found[0].startswith("-"):
                found = found[2 if found[0] in TIMEOUT_VALUED else 1:]  # `-s KILL`: two words
            found = found[1:]  # the duration
        else:
            break
    return found


def search(command):
    found = first(command)
    name = os.path.basename(found[0]) if found else ""
    return name in SEARCHES or (name == "git" and found[1:2] == ["grep"])


READERS = ("cat", "head", "tail", "nl", "less", "more", "bat")  # a Bash command that reads a file
PUNCTUATION = ";&|<>()\n"  # shell operators, split from the words around them


def tokens(command):
    """The command's words and unquoted operators (`;`, `|`, `&&`, a newline, `>`, `2`, `>&`
    ...), quotes removed; an unclosed quote: split at white space."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace, lexer.whitespace_split = " \t\r", True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def operator(token):
    return token != "" and all(char in PUNCTUATION for char in token)


def bash_read(command):
    """True for a command whose first command (as `search` finds it; it ends at an unquoted `;`,
    `|`, `&`, `&&`, `||` or a newline) reads a file and does not write its output to one: one
    of READERS, or `sed` with `-n` and without `-i` (`sed -ni` edits the file). `> f`, `f>out`,
    `1> out`, `>> f`, `&> f` and `>&f` write; `2> f` and `1>&2` do not; a reader given a
    here-document (`<<`, `<<<`) reads no file."""
    found = first(command, tokens(command))
    name = os.path.basename(found[0]) if found else ""
    own = []
    for token in found[1:]:
        if operator(token) and not token.startswith((">", "<", "&>")):
            break  # the end of the first command
        own.append(token)
    for at, token in enumerate(own):
        if not operator(token):
            continue
        if token.startswith("<<"):
            return False  # a here-document or here-string
        before = own[at - 1] if at else ""
        target = own[at + 1] if at + 1 < len(own) else ""
        if token.startswith("&>"):
            return False
        if token.startswith(">"):
            if before.isdigit() and before != "1":
                continue  # another descriptor: `2>/dev/null`, `2>&1`
            if token == ">&" and (target.isdigit() or target == "-"):
                continue  # a duplication: `1>&2`
            return False
    if name in READERS:
        return True
    flags = [re.match(r"-([A-Za-z]*)", word).group(1) for word in own
             if word.startswith("-") and not word.startswith("--")]
    if any("i" in flag for flag in flags) or any(word.startswith("--in-place") for word in own):
        return False
    return name == "sed" and ("--quiet" in own or "--silent" in own or any(
        "n" in flag for flag in flags))


HEREDOC = re.compile(r"<<(?!<)-?\s*([\"']?)([A-Za-z0-9_.-]+)\1")
WRITES = re.compile(r"\bopen\([^)]*?[\"'](?:[wax]|r\+)[bt+]*[\"']|\bwrite_(?:text|bytes)\(")
PYTHON = re.compile(r"(?:python[0-9.]*|py)(?:\.exe)?$")
TEMP = ("/tmp", "/var/tmp", "$TMPDIR", "${TMPDIR", "$TMP", "${TMP", "%TEMP%", "%TMP%")
WINDOWS_TEMP = re.compile(r"^[a-z]:[\\/]+te?mp[\\/]|[\\/]appdata[\\/]+local[\\/]+temp[\\/]", re.I)
WRAPPERS = ("env", "sudo", "nohup", "command", "exec", "xargs")  # run the next word's command
SUDO_VALUED = ("-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U", "-R", "--user",
               "--group", "--close-from", "--chdir", "--host", "--prompt", "--role", "--type",
               "--command-timeout", "--other-user", "--chroot")  # `sudo` options with a value
DECLARES = ("export", "declare", "typeset", "local", "readonly")  # `export S=x`: an assignment
VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
ENDS = (";", "|", "&", "&&", "||", "|&", ";;", "(", ")", "\n")  # end a simple command
SEDS = ("sed", "gsed")


def bodiless(command):
    """The command without its here-documents' bodies (the lines after a `<<WORD` line, up to
    the one that is WORD)."""
    kept, until = [], []
    for line in command.split("\n"):
        if until:
            if line.lstrip("\t") == until[0]:
                until.pop(0)
            continue
        kept.append(line)
        until = [found[1] for found in HEREDOC.findall(line)]
    return "\n".join(kept)


def expand(word, values):
    """The word with the `$VAR` and `${VAR}` of `values` replaced; others are kept."""
    return VARIABLE.sub(lambda m: values.get(m.group(1) or m.group(2), m.group(0)), word)


def assign(current, values):
    """`values` with the assignments of a simple command that only assigns (`S=x`, `export
    S=x`) added, a new dict; a value holding another `$` (`$(mktemp)`, a backquote) unknown."""
    words = current[1:] if current[:1] and current[0] in DECLARES else current
    if not words or not all(ASSIGNED.match(w) or w.startswith("-") for w in words):
        return values
    values = dict(values)
    for word in words:
        if ASSIGNED.match(word):
            name, _, value = word.partition("=")
            value = expand(value, values)
            if "`" in value or re.search(r"\$(?![{A-Za-z_])", value):
                values.pop(name, None)
            else:
                values[name] = value
    return values


def simple(command):
    """The command's simple commands, each (its tokens (as `tokens`) without its leading
    assignments, `timeout` and `WRAPPERS`, the variables assigned before it), split at
    `ENDS`."""
    found, current, values = [], [], {}
    for token in tokens(bodiless(command)) + [";"]:
        if token in ENDS or (operator(token) and not token.startswith(("<", ">", "&>"))):
            run = first("", current)
            while run and os.path.basename(run[0]) in WRAPPERS:
                sudo = os.path.basename(run[0]) == "sudo"
                run = first("", run[1:])
                while run and run[0].startswith("-"):
                    run = run[2 if sudo and run[0] in SUDO_VALUED else 1:]
            if run:
                found.append((run, values))
            values = assign(current, values)
            current = []
        else:
            current.append(token)
    return found


def written(target, values=None):
    """True for a target a write is a change of: not under `/dev/`, not a `.log` or `.out`
    file, not under a temp folder (`${TMPDIR:-/tmp}/x` too; a Windows one: `C:\\Temp\\`,
    `...\\AppData\\Local\\Temp\\`). `values`: the variables to expand in it first."""
    target = expand(target, values) if values else target
    if not target or operator(target) or target.startswith("/dev/"):
        return False
    if target.endswith((".log", ".out")) or WINDOWS_TEMP.search(target):
        return False
    return not any(target == t or target.startswith((t + "/", t + "\\", t + "}"))
                   or (t.startswith("${") and target.startswith((t + ":", t + "-")))
                   or (t.startswith("%") and target.startswith(t)) for t in TEMP)


def perl_in_place(own):
    """True for `perl` words with `-i` in an option cluster before the script: `-pi`, `-i.bak`;
    not a letter of a `-M`, `-I`, `-e` ... argument (`-Mstrict`, `-MList::Util=sum`)."""
    at = 0
    while at < len(own):
        word = own[at]
        if operator(word) or not word.startswith("-") or word in ("-", "--"):
            break
        for k, char in enumerate(word[1:] if not word.startswith("--") else ""):
            if char == "i":
                return True
            if char in "eE":  # the code: the rest of the word, or the next one
                at += k == len(word) - 2
                break
            if char in "MmIFxdDC":  # the rest of the word is its argument
                break
        at += 1
    return False


def changed(found, values, command):
    """True for a simple command (`simple`'s) that changes a file (see `--after-green`)."""
    name = os.path.basename(found[0])
    own = found[1:]
    flags = [w[1:] for w in own if w.startswith("-") and not w.startswith("--")]
    for at, token in enumerate(found):  # `> f.py` alone: the redirection comes first
        if not operator(token) or not token.startswith((">", "&>")):
            continue
        before = found[at - 1] if at else ""
        target = found[at + 1] if at + 1 < len(found) else ""
        if token.startswith(">") and before.isdigit() and before != "1":
            continue  # another descriptor: `2>/dev/null`, `2>&1`
        if token == ">&" and (target.isdigit() or target == "-"):
            continue  # a duplication: `>&2`
        if written(target, values):
            return True
    if name in SEDS and (any("i" in f for f in flags) or any(
            w.startswith("--in-place") for w in own)):
        return True
    if name == "perl" and perl_in_place(own):
        return True
    if name == "tee" and any(written(w, values) for w in own if not w.startswith("-")):
        return True
    if PYTHON.match(name) and WRITES.search(command):
        return True
    if name == "git":
        rest = list(own)
        while rest and rest[0].startswith("-"):
            rest = rest[2 if rest[0] in ("-C", "-c") else 1:]
        if rest[:1] == ["apply"] and not {"--check", "--stat", "--numstat"} & set(rest):
            return True
    if name == "patch" and "--dry-run" not in own:
        return True
    if name in ("mv", "cp"):
        operands = [w for w in own if not w.startswith("-") and not operator(w)]
        if "-t" in own and own.index("-t") + 1 < len(own):
            target = own[own.index("-t") + 1]
        else:
            target = operands[-1] if len(operands) >= 2 else ""
        if written(target, values):
            return True
    return False


def bash_change(command):
    """True for a Bash command that changes a file (see `--after-green`)."""
    return any(changed(run, values, command) for run, values in simple(command))


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
    unchanged, bash reads, bash read chars), (map queries, other map calls, searches)) of one
    conversation's transcript
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
    queries = others = searches = shown = shown_chars = 0
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
            if bash_read(command):
                shown += 1
                shown_chars += chars
    return by_tool, (reads, len(files), again, shown, shown_chars), (queries, others, searches)


def tool_lines(agent, found, events=None):
    if found is None:
        return [" | ".join(["tools", tag(agent)] + ["unknown"] * 5),
                " | ".join(["reads", tag(agent)] + ["unknown"] * 5),
                " | ".join(["map", tag(agent)] + ["unknown"] * 3)]
    by_tool, reads, maps = found
    held = carried(events) if events is not None else {}
    order = sorted(by_tool.items(), key=lambda item: (-held.get(item[0], 0), -item[1][1],
                                                      -item[1][0], item[0]))
    return [" | ".join(["tools", tag(agent), name] + [str(int(v)) for v in values]
                       + [str(held.get(name, 0))]) for name, values in order] \
        + [" | ".join(["reads", tag(agent)] + [str(v) for v in reads]),
           " | ".join(["map", tag(agent)] + [str(v) for v in maps])]


def text(content):
    """A tool result's text: the text itself, or its text parts joined by line breaks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content if isinstance(part, dict)
                         and part.get("type") == "text" and isinstance(part.get("text"), str))
    return ""


def kept(record):
    """The uuids a `compact_boundary` record lists as preserved (kept in the context)."""
    meta = record.get("compactMetadata")
    meta = meta.get("preservedMessages") if isinstance(meta, dict) else None
    found = set()
    for key in ("uuids", "allUuids"):
        given = meta.get(key) if isinstance(meta, dict) else None
        if isinstance(given, list):
            found.update(u for u in given if isinstance(u, str))
    return found


def timeline(paths, since=None):
    """One conversation's transcript files as events in time order (records without a time
    last, then in file order), or None when no file can be read. Each event is a dict with
    `kind`: `request` (`prompt`, `output`), `call` (`id`, `name`, `input`), `result` (`id`,
    `chars`, `error`, `head`: its first line, `tail`: its last non-blank line, `uuid`: its
    record's) or `compact` (`kept`: the uuids it preserved). A request, call or result in two
    files counts once, at its first record; `since` as in `read`."""
    requests, calls, results, compactions, opened, seq = {}, {}, {}, [], False, 0
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
                    seq += 1
                    place = (at is None, at or 0, seq)
                    if record.get("type") == "system" \
                            and record.get("subtype") == "compact_boundary":
                        compactions.append((place, {"kind": "compact", "kept": kept(record)}))
                    found = request(record)
                    if found:
                        key, use, _ = found
                        entry = requests.setdefault(key, [place, None])
                        entry[0] = min(entry[0], place)
                        entry[1] = use  # the last record's: the complete one
                    for n, use in enumerate(blocks(record, "tool_use")):
                        key = use.get("id")
                        key = key if isinstance(key, str) else object()  # no id: its own call
                        given = use.get("input")
                        calls.setdefault(key, (place + (n + 1,), {
                            "kind": "call", "id": key, "name": use.get("name"),
                            "input": given if isinstance(given, dict) else {}}))
                    for done in blocks(record, "tool_result"):
                        key = done.get("tool_use_id")
                        if not isinstance(key, str) or key in results:
                            continue
                        said = text(done.get("content"))
                        rest = [part for part in said.splitlines() if part.strip()]
                        results[key] = (place + (0,), {
                            "kind": "result", "id": key, "chars": size(done.get("content")),
                            "error": done.get("is_error") is True,
                            "head": said.splitlines()[0] if said else "",
                            "tail": rest[-1].strip() if rest else "", "uuid": record.get("uuid")})
        except OSError:
            continue
    if not opened:
        return None
    events = [(place + (0,), {"kind": "request",
                              "prompt": sum(count(use, key) for key in PROMPT),
                              "output": count(use, "output_tokens")})
              for place, use in requests.values()]
    events += [(place + (0,), event) for place, event in compactions]
    events += list(calls.values()) + list(results.values())
    events.sort(key=lambda item: item[0])
    return [event for _, event in events]


def counted(events):
    """{call id: tool name} of the calls counted, and before[i]: the requests among events[:i]."""
    names = {e["id"]: e["name"] for e in events if e["kind"] == "call"}
    before = [0]
    for event in events:
        before.append(before[-1] + (event["kind"] == "request"))
    return names, before


def carried(events):
    """{tool: carried chars}: each counted result's characters times the requests after it,
    up to the first compaction that did not preserve its record (see `--tools`)."""
    names, before = counted(events)
    marks = [i for i, event in enumerate(events) if event["kind"] == "compact"]
    held = {}
    for at, event in enumerate(events):
        if event["kind"] != "result" or event["id"] not in names:
            continue
        # The compactions after it, in order, until one that dropped it: no scan of the events.
        stop = next((marks[j] for j in range(bisect.bisect_right(marks, at), len(marks))
                     if event["uuid"] not in events[marks[j]]["kept"]), len(events))
        name = tag(names[event["id"]])
        held[name] = held.get(name, 0) + event["chars"] * (before[stop] - before[at + 1])
    return held


def prefix_line(agent, events):
    if events is None:
        return " | ".join(["prefix", tag(agent)] + ["unknown"] * 3)
    prompts = [e["prompt"] for e in events if e["kind"] == "request"]
    if not prompts:
        return " | ".join(["prefix", tag(agent), "none"])
    total = sum(prompts)
    share = "%.1f" % min(100.0, 100.0 * prompts[0] * len(prompts) / total) if total \
        else "unknown"
    return " | ".join(["prefix", tag(agent), str(prompts[0]), str(total), share])


TESTS = re.compile(r"\b(?:unittest|pytest|ctest)\b(?!\.)|\bmake (?:test|check)\b"
                   r"|\b(?:npm(?: run)?|yarn|pnpm|go|cargo|mvn|gradle) test\b")
LOGGED = re.compile(r">>?\s*[^\s;&|]+\.log\b.*\becho \$\?", re.S)


def green(event, result):
    """True for a Bash call that runs a test or validation command that passed (see
    `--after-green`)."""
    command = event["input"].get("command")
    if event["name"] != "Bash" or not isinstance(command, str) or result is None:
        return False
    if LOGGED.search(command):  # the status is printed, the call itself does not fail
        return not result["error"] and result["tail"] == "0"
    return bool(TESTS.search(command)) and not result["error"]


def test_run(run):
    """True for a simple command (`simple`'s) that runs a test: `TESTS` in its words before a
    redirection, not one of the commands that change a file by their own words."""
    words = next((run[:at] for at, w in enumerate(run) if operator(w)), run)
    return os.path.basename(run[0]) not in SEDS + ("perl", "tee", "mv", "cp", "git", "patch") \
        and bool(TESTS.search(" ".join(words)))


def tested_after(command):
    """True for a command that runs its test after its last change (`sed -i ... && pytest`;
    not `pytest && sed -i ...`), as `green` finds a test in the simple commands after it. A
    test run is no change here: its output written to a file, or the whole-text Python rule
    (`python3 -m pytest` beside a Python edit)."""
    found = simple(command)
    at = max((at for at, (run, values) in enumerate(found) if changed(run, values, command)
              and not test_run(run)), default=-1)
    rest = " ; ".join(" ".join(run) for run, _ in found[at + 1:])
    return bool(TESTS.search(rest) or LOGGED.search(rest))


def changes(event):
    """True for a call that changes a file: an edit tool's, or a Bash change."""
    command = event["input"].get("command")
    return event["name"] in EDITS or (event["name"] == "Bash" and isinstance(command, str)
                                      and bash_change(command))


def after_green_line(agent, events):
    if events is None:
        return " | ".join(["after green", tag(agent), "unknown"])
    results = {e["id"]: e for e in events if e["kind"] == "result"}
    _, before = counted(events)
    edited = max((at for at, e in enumerate(events) if e["kind"] == "call"
                  and changes(e) and not results.get(e["id"], {}).get("error")),
                 default=None)
    found = None if edited is None else next(  # a Bash change can be its own green
        (at for at in range(edited, len(events)) if events[at]["kind"] == "call"
         and green(events[at], results.get(events[at]["id"])) and (
             at > edited or tested_after(events[at]["input"]["command"]))), None)
    if found is None:
        return " | ".join(["after green", tag(agent), "none"])
    later = events[found + 1:]
    asked = [e for e in later if e["kind"] == "request"]
    return " | ".join(["after green", tag(agent), "%d of %d" % (before[found], before[-1]),
                       str(len(asked)), str(sum(e["kind"] == "call" for e in later)),
                       str(sum(e["output"] for e in asked)), str(sum(e["prompt"] for e in asked))])


NORMAL = ((re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`"), "Q"),  # quoted strings
          (re.compile(r"(?:[A-Za-z]:)?[\w.~-]*[/\\][^\s:,;()\[\]]*"), "P"),  # paths
          (re.compile(r"\b(?:0x)?(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{6,}\b"),
           "H"),  # hex ids
          (re.compile(r"\d+"), "N"))


def signature(name, line):
    """An error's signature: its tool and its first line without quoted strings, paths, hex ids
    and digits."""
    for pattern, mark in NORMAL:
        line = pattern.sub(mark, line)
    return tag(name), " ".join(line.split())


def error_line(agent, events):
    if events is None:
        return " | ".join(["errors", tag(agent)] + ["unknown"] * 4)
    names, before = counted(events)
    seen, errors, repeated, first_repeat = set(), 0, 0, None
    for at, event in enumerate(events):
        if event["kind"] != "result" or not event["error"] or event["id"] not in names:
            continue
        errors += 1
        mark = signature(names[event["id"]], event["head"])
        if mark in seen:
            repeated += 1
            first_repeat = at if first_repeat is None else first_repeat
        seen.add(mark)
    after = 0 if first_repeat is None else before[-1] - before[first_repeat + 1]
    return " | ".join(["errors", tag(agent)] + [str(v) for v in (errors, len(seen), repeated,
                                                                  after)])


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
                         "calls in a row that each ended in an error, and the longest; then an "
                         "`errors` line: errors, distinct signatures, repeats")
    ap.add_argument("--tools", action="store_true",
                    help="after each agent's lines, its `tools` lines (calls, result characters "
                         "errors and carried characters by tool), a `reads` line and a `map` "
                         "line")
    ap.add_argument("--prefix", action="store_true",
                    help="after each agent's lines, a `prefix` line: its first request's input "
                         "tokens, all its requests' and the first one's share")
    ap.add_argument("--after-green", action="store_true",
                    help="after each agent's lines, an `after green` line: what it spent after "
                         "its last change passed a test command")
    args = ap.parse_intermixed_args(argv)
    expected = dict(args.agents)  # the last =MODEL given for an agent
    for row in rows(args.session, [name for name, _ in args.agents], args.since):
        print(render(*row, expected=expected.get(row[0], ())))
        files = paths(args.session, row[0])
        events = timeline(files, args.since) \
            if args.streaks or args.tools or args.prefix or args.after_green else None
        if args.streaks:
            print(streak_line(row[0], streaks(files, args.since)))
            print(error_line(row[0], events))
        if args.tools:
            for line in tool_lines(row[0], tools(files, args.since), events):
                print(line)
        if args.prefix:
            print(prefix_line(row[0], events))
        if args.after_green:
            print(after_green_line(row[0], events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
