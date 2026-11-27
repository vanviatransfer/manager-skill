"""Tests for usage.py, on a synthetic session written into a temporary Claude config folder:
python3 -m unittest discover -s <this folder>"""
import contextlib
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))  # portability.py, in the plugin folder
import portability  # noqa: E402
import usage  # noqa: E402

SCRIPT = os.path.join(HERE, "usage.py")
SESSION = "0f3c9a1e-5b7d-4c2a-9e1f-0123456789ab"
UNKNOWN = " | unknown" * 11

# What the fixture below adds up to, by hand.
ORCHESTRATOR = "usage | orchestrator | main | model-c | 4 | 10 | 47000 | 400 | 35500 | 650 | " \
               "21352 | 1 | 1 | 5020"
REVIEWER = "usage | b2 | manager-plugin:reviewer | model-b | 2 | 5 | 7000 | 7500 | 0 | 1100 | " \
           "8402 | 0 | 0 | 92"
IMPLEMENTER = "usage | a1 | manager-plugin:implementer | model-a | 7 | 17 | 29250 | 24600 | 0 | " \
              "5680 | 3092 | 1 | 1 | 900"
UNTIMED = "usage | c3 | unknown | model-a | 1 | 5 | 0 | 800 | 0 | 20 | 825 | unknown | unknown | " \
          "unknown"


# The bounded lines (`--since`) of the same fixture, from the fixture's second 400 and 1700.
RUN = "usage | orchestrator | main | model-c | 3 | 6 | 47000 | 400 | 15500 | 350 | 21352 | 0 | " \
      "1 | 4620"
ROUND = "usage | a1 | manager-plugin:implementer | model-a | 4 | 10 | 10950 | 15100 | 0 | 5130 | " \
        "3092 | 0 | 0 | 200"
NOTHING = " | unknown | 0 | 0 | 0 | 0 | 0 | 0 | unknown | unknown | unknown | unknown"


def stamp(seconds):
    moment = datetime.datetime(2026, 1, 1, 9, 0, 0) + datetime.timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def epoch(seconds):
    """The time `stamp(seconds)` names, as a file's modification time has it."""
    zero = datetime.datetime(2026, 1, 1, 9, 0, 0, tzinfo=datetime.timezone.utc)
    return zero.timestamp() + seconds


def other(at, kind="user", **fields):
    """A record that is not a request: a prompt, a system line."""
    record = dict({"type": kind, "message": {"role": "user", "content": "text"}}, **fields)
    if at is not None:
        record["timestamp"] = stamp(at)
    return [record]


def result(at, **fields):
    """A tool result: a `user` record too, but no prompt."""
    return other(at, message={"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "text"}]}, **fields)


def request(at, key, fresh, cached, written, output, hour=0, blocks=1, model="model-a",
            split=True):
    """One request as a transcript holds it: a record per content block, each with the request's
    message id and usage (here the earlier ones with the output still at 1) and stamped when the
    block ends (here the first at `at`): later than the prompt or tool result that started it."""
    records = []
    for block in range(blocks):
        use = {"input_tokens": fresh, "cache_read_input_tokens": cached,
               "cache_creation_input_tokens": written, "service_tier": "standard",
               "output_tokens": output if block == blocks - 1 else 1,
               "server_tool_use": {"web_search_requests": 0}, "iterations": [{}]}
        if split:
            use["cache_creation"] = {"ephemeral_5m_input_tokens": written - hour,
                                     "ephemeral_1h_input_tokens": hour}
        record = {"type": "assistant", "requestId": "req-" + key, "isSidechain": True,
                  "message": {"id": key, "model": model, "role": "assistant", "usage": use,
                              "content": [{"type": "text", "text": "text"}]}}
        if at is not None:
            record["timestamp"] = stamp(at + block)
        records.append(record)
    return records


def lines(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = usage.main(list(args))
    assert code == 0, code
    return out.getvalue().splitlines()


def tree(root):
    found = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            found[path] = (os.path.getsize(path), os.stat(path).st_mtime_ns)
    return found


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.config = os.path.join(self.tmp, "config [1] folder")
        patch = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.config})
        patch.start()
        self.addCleanup(patch.stop)
        # The session began in one working folder and went on in another (which sorts first).
        self.old = os.path.join(self.config, "projects", "-work-old")
        self.new = os.path.join(self.config, "projects", "-work-new")
        waited = request(410, "o2", 2, 20000, 600, 100, hour=500)
        self.write(self.old, SESSION + ".jsonl", (
            other(0),
            request(10, "o1", 4, 0, 20000, 300, hour=20000, blocks=3),
            result(400),  # a subagent returns 388 s after o1: the 1-hour cache is still there
            waited))
        self.write(self.new, SESSION + ".jsonl", (
            waited,  # the same request, in both files
            other(5000),  # the owner answers after 4,590 s: only a shared prefix is still cached
            request(5010, "o3", 2, 6000, 15000, 200, hour=15000),
            request(5020, "o4", 2, 21000, 300, 50, split=False, model="model-c")))
        self.write(self.new, "another-session.jsonl", (request(20, "x1", 9, 9, 9, 9),))
        self.agent(self.old, "b2", "manager-plugin:reviewer", (
            other(500),
            request(510, "r1", 3, 0, 7000, 200, model="model-b"),
            result(520),  # a tool result 10 s after r1: r2 is sent at once
            # ... and thinks for 70 s before its first block ends: its own time, not a resume
            request(590, "r2", 2, 7000, 500, 900, blocks=3, model="model-b")))
        self.agent(self.new, "a1", "manager-plugin:implementer", (
            other(1000),
            request(1005, "m1", 3, 0, 9000, 100, blocks=2),
            result(1020),  # 14 s after m1: not a resume
            request(1025, "m2", 2, 9000, 300, 50),
            other(1220),  # a message 195 s after m2, and m3 reads the context: warm
            request(1225, "m3", 2, 9300, 200, 400),
            other(1700),  # a message 475 s after m3, and m4 writes it again: cold
            request(1705, "m4", 4, 0, 9950, 60, blocks=2),
            request(1710, "m5", 2, 9950, 100, 5000),
            other(1800, kind="system", subtype="compact_boundary"),
            other(1801, isCompactSummary=True),  # 91 s after m5, but a compaction: not counted
            request(1805, "m6", 2, 1000, 2000, 30),
            request(1825, "m7", 2, 0, 3050, 40),  # nothing read, but nothing new started it
            request(1830, "e1", 0, 0, 0, 0, model="<synthetic>"),  # an error message
            other(1900)),
            junk=("not json\n", "\n", "[1, 2]\n", '"text"\n', '{"type": "assistant"\n',
                  '{"type": "assistant", "message": "text"}\n',
                  '{"type": "assistant", "message": {"usage": {"output_tokens": 7}}}\n',
                  '{"type": "assistant", "message": {"id": "u1", "usage": "n/a"}}\n',
                  '{"type": "user", "message": {"id": "u2", "usage": {"output_tokens": 7}}}\n'))
        self.agent(self.new, "c3", None, (other(None), request(None, "n1", 5, 0, 800, 20,
                                                               split=False)))
        self.write(os.path.join(self.new, SESSION, "subagents"), "agent-a1.prefix.json", ())
        self.write(os.path.join(self.new, SESSION, "subagents"), "notes-agent-zz.jsonl",
                   (request(30, "z1", 9, 9, 9, 9),))

    def write(self, folder, name, groups, junk=()):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as fh:
            for group in groups:
                for record in group:
                    fh.write(json.dumps(record) + "\n")
            fh.writelines(junk)
        return os.path.join(folder, name)

    def agent(self, project, name, kind, groups, junk=()):
        folder = os.path.join(project, SESSION, "subagents")
        path = self.write(folder, "agent-%s.jsonl" % name, groups, junk)
        if kind:
            with open(os.path.join(folder, "agent-%s.meta.json" % name), "w",
                      encoding="utf-8") as fh:
                json.dump({"agentType": kind, "description": "words that are never printed"}, fh)
        return path


class UsageTest(Fixture):
    def test_the_session_orchestrator_first_then_its_subagents_oldest_first(self):
        self.assertEqual(lines(SESSION), [ORCHESTRATOR, REVIEWER, IMPLEMENTER, UNTIMED])

    def test_named_agents_only_in_the_order_named(self):
        self.assertEqual(lines(SESSION, "a1"), [IMPLEMENTER])
        self.assertEqual(lines(SESSION, "orchestrator"), [ORCHESTRATOR])
        self.assertEqual(lines(SESSION, "c3", "orchestrator", "b2", "c3"),
                         [UNTIMED, ORCHESTRATOR, REVIEWER])

    def test_every_line_has_the_documented_fields(self):
        for line in lines(SESSION) + lines("no-such-session", "a1"):
            self.assertEqual(len(line.split(" | ")), 1 + len(usage.COLUMNS), line)
        row = "usage | " + " | ".join(usage.COLUMNS)
        self.assertIn(row, " ".join(usage.__doc__.split()))
        with open(os.path.join(HERE, "..", "references", "run-record.md"), encoding="utf-8") as fh:
            record = fh.read()
        self.assertIn("\n%s\n" % row, record)  # the run record's column line
        record_text = " ".join(record.split())
        self.assertIn('`<python> "${CLAUDE_SKILL_DIR}/scripts/usage.py" <session id> '
                      '<agent>[=<model>]... >> <file>`', record_text)
        self.assertIn("ending `!=<model>` when a request ran on another", record_text)
        self.assertIn("`orchestrator --since <the **Run marker** file>`", record_text)
        for column in usage.COLUMNS:  # each one is defined there
            self.assertIn("`%s`" % column, record.split("\n## Usage lines\n")[1])

    def test_what_is_missing_is_unknown(self):
        self.assertEqual(lines("no-such-session"), ["usage | orchestrator | main" + UNKNOWN])
        self.assertEqual(lines("no-such-session", "a1"), ["usage | a1 | unknown" + UNKNOWN])
        self.assertEqual(lines(SESSION, "zz"), ["usage | zz | unknown" + UNKNOWN])
        self.agent(self.new, "d4", "manager-plugin:worker", ())
        os.remove(os.path.join(self.new, SESSION, "subagents", "agent-d4.jsonl"))
        self.assertEqual(lines(SESSION, "d4"), ["usage | d4 | manager-plugin:worker" + UNKNOWN])
        for project in (self.old, self.new):  # without the main conversation's files
            os.remove(os.path.join(project, SESSION + ".jsonl"))
        self.assertEqual(lines(SESSION), ["usage | orchestrator | main" + UNKNOWN, REVIEWER,
                                          IMPLEMENTER, UNTIMED])
        shutil.rmtree(self.config)
        self.assertEqual(lines(SESSION), ["usage | orchestrator | main" + UNKNOWN])

    def test_a_name_is_never_a_path_or_a_pattern(self):
        os.mkdir(os.path.join(self.new, SESSION, "subagents", "agent-x"))
        self.assertEqual(lines(SESSION, "x/../agent-a1", "a*", "a1.meta", ""),
                         ["usage | x_.._agent-a1 | unknown" + UNKNOWN,
                          "usage | a_ | unknown" + UNKNOWN, "usage | a1.meta | unknown" + UNKNOWN,
                          "usage | unknown | unknown" + UNKNOWN])
        for session in ("*", SESSION[:8] + "*", "../-work-new/" + SESSION, SESSION + ".jsonl",
                        "[0-9a-f-]*", ""):
            self.assertEqual(lines(session, "orchestrator", "a1"),
                             ["usage | orchestrator | main" + UNKNOWN,
                              "usage | a1 | unknown" + UNKNOWN], session)

    def test_a_transcript_that_cannot_be_understood_counts_nothing(self):
        bad = {"input_tokens": "9", "cache_read_input_tokens": -5, "output_tokens": True,
               "cache_creation_input_tokens": 2.5, "cache_creation": "text"}
        path = self.write(os.path.join(self.new, SESSION, "subagents"), "agent-e5.jsonl", (), junk=(
            "{}\n", "null\n",
            json.dumps({"type": "assistant", "timestamp": 7, "message": {
                "id": "b1", "model": ["a list"], "usage": bad}}) + "\n",
            json.dumps({"type": "assistant", "timestamp": "yesterday", "message": {
                "id": "b2", "model": "model | a\nb", "usage": {"cache_creation": {
                    "ephemeral_1h_input_tokens": 50}}}}) + "\n"))
        with open(path, "ab") as fh:
            fh.write(b"\xff\xfe not utf-8 \x00\n")
        self.assertEqual(lines(SESSION, "e5"), [
            "usage | e5 | unknown | model_a_b | 2 | 0 | 0 | 0 | 0 | 0 | 0 | unknown | unknown | "
            "unknown"])
        self.agent(self.new, "f6", ["not a type"], ())
        self.assertEqual(lines(SESSION, "f6"), [
            "usage | f6 | unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | unknown | unknown | unknown"
            " | unknown"])

    def test_the_default_config_folder_is_dot_claude_at_home(self):
        home = os.path.join(self.tmp, "home")
        os.makedirs(home)
        os.rename(self.config, os.path.join(home, ".claude"))
        self.assertEqual(lines(SESSION, "b2"), ["usage | b2 | unknown" + UNKNOWN])
        with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home,
                                          "CLAUDE_CONFIG_DIR": ""}):
            self.assertEqual(lines(SESSION, "b2"), [REVIEWER])
            del os.environ["CLAUDE_CONFIG_DIR"]
            self.assertEqual(lines(SESSION, "b2"), [REVIEWER])

    def test_the_command_prints_the_lines_and_writes_nothing(self):
        before = tree(self.tmp), sorted(os.listdir(HERE))
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config)
        for args, expected in (([SESSION], [ORCHESTRATOR, REVIEWER, IMPLEMENTER, UNTIMED]),
                               ([SESSION, "a1", "zz"], [IMPLEMENTER,
                                                        "usage | zz | unknown" + UNKNOWN]),
                               (["no-such-session"], ["usage | orchestrator | main" + UNKNOWN])):
            p = subprocess.run([sys.executable, "-I", "-B", SCRIPT] + args, capture_output=True,
                               env=env, cwd=self.tmp)
            self.assertEqual((p.returncode, p.stderr.decode()), (0, ""), args)
            self.assertEqual(p.stdout.decode("ascii").splitlines(), expected)
        p = subprocess.run([sys.executable, "-I", "-B", SCRIPT], capture_output=True, env=env,
                           cwd=self.tmp)
        self.assertEqual((p.returncode, p.stdout), (2, b""))
        self.assertEqual((tree(self.tmp), sorted(os.listdir(HERE))), before)


class SinceTest(Fixture):
    """`--since WHEN`: only the records stamped at or after a file's modification time (the run
    marker's: the run, not the whole session) or an ISO 8601 time."""

    def marker(self, seconds, name="marker"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("R2026-01-01-0906\n")
        os.utime(path, (epoch(seconds), epoch(seconds)))
        return path

    def test_the_orchestrator_line_counts_the_run_from_its_marker(self):
        marker = self.marker(400)
        self.assertEqual(lines(SESSION, "orchestrator", "--since", marker), [RUN])
        self.assertEqual(lines(SESSION, "orchestrator"), [ORCHESTRATOR])  # the whole session
        # A request counts whole with one record at or after the bound: o1's last, at second 12.
        for seconds, expected in ((12, ORCHESTRATOR.replace("5020", "5008")), (13, RUN)):
            self.assertEqual(lines(SESSION, "orchestrator", "--since", self.marker(seconds)),
                             [expected], seconds)

    def test_a_time_bounds_as_a_file_does(self):
        for text in (stamp(400), "2026-01-01T09:06:40+00:00", "2026-01-01T11:06:40.000+02:00"):
            self.assertEqual(lines(SESSION, "orchestrator", "--since", text), [RUN], text)
        local = datetime.datetime.fromtimestamp(epoch(400)).isoformat()  # no zone: local time
        self.assertEqual(lines(SESSION, "orchestrator", "--since", local), [RUN])
        self.assertEqual(usage.moment(stamp(400)), epoch(400))
        self.assertEqual(usage.moment(self.marker(400)), epoch(400))

    def test_the_option_stands_anywhere_and_bounds_every_line(self):
        marker = self.marker(1700)
        for args in ((SESSION, "a1", "--since", marker), (SESSION, "--since", marker, "a1"),
                     ("--since", marker, SESSION, "a1"), ("--since=" + marker, SESSION, "a1")):
            self.assertEqual(lines(*args), [ROUND], args)
        self.assertEqual(lines(SESSION, "--since", marker), [
            "usage | orchestrator | main | model-c | 2 | 4 | 27000 | 300 | 15000 | 250 | 21352 | "
            "0 | 0 | 20", ROUND, "usage | b2 | manager-plugin:reviewer" + NOTHING,
            "usage | c3 | unknown" + NOTHING])

    def test_a_record_without_a_time_is_not_counted(self):
        self.assertEqual(lines(SESSION, "c3"), [UNTIMED])
        self.assertEqual(lines(SESSION, "c3", "--since", stamp(0)), ["usage | c3 | unknown"
                                                                    + NOTHING])
        self.assertEqual(lines(SESSION, "orchestrator", "--since", stamp(9000)),
                         ["usage | orchestrator | main" + NOTHING])
        self.assertEqual(lines(SESSION, "zz", "--since", stamp(0)),
                         ["usage | zz | unknown" + UNKNOWN])

    def test_the_first_request_counted_is_no_resume(self):
        path = self.write(self.tmp, "one.jsonl", (
            other(0), request(5, "p1", 0, 0, 10000, 10),
            other(600), request(605, "p2", 0, 0, 10010, 10),
            other(1200), request(1205, "p3", 0, 10010, 10, 10)))
        for since, expected in ((None, (3, 1, 1, 1205)), (epoch(600), (2, 1, 0, 605)),
                                (epoch(601), (2, 1, 0, 600)), (epoch(1205), (1, 0, 0, 0))):
            totals = usage.read([path], since)
            self.assertEqual(tuple(totals[key] for key in ("requests", "warm", "cold", "seconds")),
                             expected, since)

    def test_a_bound_that_cannot_be_read_prints_no_line(self):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config)
        for value in (os.path.join(self.tmp, "no-marker"), "yesterday", ""):
            p = subprocess.run([sys.executable, "-I", "-B", SCRIPT, SESSION, "orchestrator",
                                "--since", value], capture_output=True, env=env, cwd=self.tmp)
            self.assertEqual((p.returncode, p.stdout), (2, b""), value)
            self.assertIn("neither a file nor an ISO 8601 time", p.stderr.decode())
        p = subprocess.run([sys.executable, "-I", "-B", SCRIPT, SESSION, "orchestrator",
                            "--since", self.marker(400)], capture_output=True, env=env,
                           cwd=self.tmp)
        self.assertEqual((p.returncode, p.stdout.decode().splitlines(), p.stderr), (0, [RUN], b""))


class LastRequestTest(Fixture):
    """`last`: the context size at a transcript's last request, read from the file's end only."""

    def path(self, *groups, **kw):
        return self.write(self.tmp, "one.jsonl", groups, **kw)

    def test_it_is_the_context_at_return(self):
        for path in (os.path.join(self.new, SESSION + ".jsonl"),
                     os.path.join(self.old, SESSION, "subagents", "agent-b2.jsonl"),
                     os.path.join(self.new, SESSION, "subagents", "agent-a1.jsonl"),
                     os.path.join(self.new, SESSION, "subagents", "agent-c3.jsonl")):
            self.assertEqual(usage.last(path), usage.read([path])["context"], path)
        self.assertEqual(usage.last(os.path.join(self.new, SESSION + ".jsonl")), 21352)

    def test_the_last_request_counts_not_the_largest(self):
        big, small = request(5, "p1", 5, 300000, 2000, 400), request(905, "p2", 3, 0, 9000, 20)
        self.assertEqual(usage.last(self.path(other(0), big)), 302405)
        self.assertEqual(usage.last(self.path(other(0), big, other(900), small)), 9023)
        # Its last record is the complete one; what follows it is no request.
        blocks = request(5, "p3", 4, 100, 200, 3000, blocks=3)
        self.assertEqual(usage.last(self.path(other(0), blocks)), 3304)
        self.assertEqual(usage.last(self.path(other(0), blocks[:2])), 305)
        after = (result(9, toolUseResult={"usage": {"input_tokens": 999999}}),
                 other(10, kind="attachment"), request(11, "e1", 0, 0, 0, 0, model="<synthetic>"),
                 other(12, kind="system", subtype="stop_hook_summary"))
        self.assertEqual(usage.last(self.path(other(0), blocks, *after)), 3304)
        self.assertEqual(usage.last(self.path(other(0), blocks, *after, junk=(
            "not json\n", "\n", '"usage"\n', '[{"usage": 1}]\n', '{"type": "assistant"\n',
            '{"type": "assistant", "message": {"usage": {"output_tokens": 7}}}\n',
            '{"type": "user", "message": {"id": "u2", "usage": {"output_tokens": 7}}}\n'))), 3304)

    def test_only_the_end_of_the_file_is_read(self):
        early, late = request(5, "p1", 1, 2, 3, 4), request(9, "p2", 10, 20, 30, 40)
        padding = other(6, text="x" * 5000)
        path = self.path(early, padding, late)
        size, cut = os.path.getsize(path), len(json.dumps(late[0])) + 1
        self.assertEqual(usage.last(path), 100)
        self.assertEqual(usage.last(path, cut), 100)  # the whole record, from its first byte
        self.assertEqual(usage.last(path, cut + 1), 100)  # after the cut: a part of a line
        self.assertEqual(usage.last(path, cut - 1), None)  # a record cut short is not read
        path = self.path(early, padding)
        self.assertEqual(usage.last(path), 10)
        self.assertEqual(usage.last(path, 5000), None)  # the request lies before the end read
        self.assertEqual(usage.last(path, size), 10)

    def test_nothing_to_read_is_none(self):
        self.assertIsNone(usage.last(os.path.join(self.tmp, "no-such-file.jsonl")))
        self.assertIsNone(usage.last(self.tmp))  # a folder
        self.assertIsNone(usage.last("bad\0name"))
        self.assertIsNone(usage.last(self.path()))  # an empty file
        self.assertIsNone(usage.last(self.path(other(0), result(5))))
        self.assertIsNone(usage.last(self.path(junk=("not json\n", b"\xff\xfe".decode("latin-1")))))
        path = self.path(request(5, "p1", 1, 2, 3, 4))
        with open(path, "ab") as fh:
            fh.write(b'\xff\xfe "usage" not utf-8 \x00\n')
        self.assertEqual(usage.last(path), 10)
        before = tree(self.tmp), sorted(os.listdir(HERE))
        usage.last(path)
        self.assertEqual((tree(self.tmp), sorted(os.listdir(HERE))), before)


class ResumeTest(Fixture):
    """A resume: a request sent 60 s or more after the agent's previous one ended, by the prompt
    or tool result that started it (for a subagent: by a prompt only). Cold: under half of the
    previous prompt read from the cache. The first request after a compaction is not counted."""

    def resumes(self, *groups, **kw):
        path = self.write(self.tmp, "one.jsonl", groups)
        totals = usage.read([path], **kw)
        return totals["warm"], totals["cold"]

    def test_a_subagents_long_tool_call_is_no_resume(self):
        first = other(0) + request(5, "p1", 0, 0, 10000, 10)
        warm, cold = request(400, "p2", 0, 10000, 10, 10), request(400, "p2", 0, 0, 10010, 10)
        for started, expected in ((result(395), (0, 0)), (other(395), (1, 0)),
                                  (other(395, message={"role": "user", "content": [
                                      {"type": "text", "text": "a message"}]}), (1, 0)),
                                  (other(395, isMeta=True, origin={"kind": "coordinator"}), (1, 0)),
                                  (other(100) + result(395), (0, 0)),
                                  (result(100) + other(395), (1, 0)),
                                  (other(395) + result(396), (0, 0))):
            self.assertEqual(self.resumes(first, started, warm, waits=False), expected, started)
            self.assertEqual(self.resumes(first, started, cold, waits=False), expected[::-1])
            self.assertEqual(self.resumes(first, started, warm), (1, 0))  # the orchestrator's
        # A record that is not understood is no tool result.
        for content in (None, 7, [], ["tool_result"], [{"type": "text"}], {"type": "tool_result"}):
            odd = other(395, message={"role": "user", "content": content})
            self.assertEqual(self.resumes(first, odd, warm, waits=False), (1, 0), content)
        self.assertEqual(self.resumes(first, other(395, message="text"), warm, waits=False),
                         (1, 0))

    def test_the_lines_count_a_tool_wait_for_the_orchestrator_only(self):
        groups = (other(0), request(5, "t1", 0, 0, 10000, 10),
                  result(300), request(305, "t2", 0, 10000, 10, 10),  # a 295 s tool call
                  other(900), request(905, "t3", 0, 10010, 10, 10),  # a message 595 s later
                  result(2000), request(2005, "t4", 0, 0, 10030, 10))  # a 1,095 s tool call
        self.agent(self.new, "g7", "manager-plugin:implementer", groups)
        self.write(self.new, "tool-waits.jsonl", groups)
        counted = " | model-a | 4 | 0 | 20010 | 20050 | 0 | 40 | 10040 | "
        self.assertEqual(lines(SESSION, "g7"), [
            "usage | g7 | manager-plugin:implementer" + counted + "1 | 0 | 2005"])
        self.assertEqual(lines("tool-waits", "orchestrator"), [
            "usage | orchestrator | main" + counted + "2 | 1 | 2005"])

    def test_the_gap_runs_from_the_previous_requests_last_record_to_what_started_this_one(self):
        first = other(0) + request(5, "p1", 0, 0, 10000, 10, blocks=3)  # its last record: at 7 s
        warm, cold = request(70, "p2", 0, 10000, 10, 10), request(70, "p2", 0, 0, 10010, 10)
        self.assertEqual(self.resumes(first, other(66), warm), (0, 0))
        self.assertEqual(self.resumes(first, other(67), warm), (1, 0))
        self.assertEqual(self.resumes(first, other(66), cold), (0, 0))
        self.assertEqual(self.resumes(first, other(67), cold), (0, 1))
        # Several tool results: the last one before the request started it.
        self.assertEqual(self.resumes(first, other(8), other(67), warm), (1, 0))
        self.assertEqual(self.resumes(first, other(8), warm, other(75)), (0, 0))

    def test_a_requests_own_time_is_not_a_gap(self):
        first = other(0) + request(5, "p1", 3, 0, 9000, 10)
        slow = request(80, "p2", 0, 9000, 300, 10)  # its only record: 75 s after p1's
        self.assertEqual(self.resumes(first, other(6), slow), (0, 0))  # sent at 6 s
        self.assertEqual(self.resumes(first, other(6), request(80, "p2", 0, 0, 9300, 10)), (0, 0))
        self.assertEqual(self.resumes(first, other(65), slow), (1, 0))
        self.assertEqual(self.resumes(first, slow), (0, 0))  # no record of what started it
        # A prompt or a tool result starts a request, no other record does.
        self.assertEqual(self.resumes(first, other(6), other(70, kind="attachment"),
                                      other(71, kind="system", subtype="stop_hook_summary"),
                                      slow), (0, 0))
        self.assertEqual(self.resumes(first, other(6), slow, other(85),
                                      request(700, "p3", 0, 9300, 10, 10)), (0, 0))

    def test_cold_is_under_half_of_the_previous_prompt(self):
        first = other(0) + request(5, "p1", 0, 0, 10000, 10)
        for cached, expected in ((10000, (1, 0)), (5000, (1, 0)), (4999, (0, 1)), (0, (0, 1))):
            again = other(600) + request(605, "p2", 10, cached, 10000 - cached, 10)
            self.assertEqual(self.resumes(first, again), expected, cached)
        grown = request(605, "p2", 0, 10000, 30000, 10)  # a long tool result: all read, more new
        self.assertEqual(self.resumes(first, other(600), grown), (1, 0))

    def test_a_smaller_prompt_is_not_a_compaction(self):
        first = other(0) + request(5, "p1", 0, 0, 455000, 10)
        again = other(80000) + request(80005, "p2", 0, 46000, 372000, 10)
        self.assertEqual(self.resumes(first, again), (0, 1))
        self.assertEqual(self.resumes(first, other(80000),
                                      request(80005, "p2", 0, 400000, 18000, 10)), (1, 0))

    def test_the_first_request_after_a_compaction_is_not_counted(self):
        boundary = other(100, kind="system", subtype="compact_boundary")
        first = other(0) + request(5, "p1", 0, 0, 10000, 10)
        small = other(99, isCompactSummary=True) + request(105, "p2", 0, 1000, 2000, 10)
        self.assertEqual(self.resumes(first, small), (0, 1))
        self.assertEqual(self.resumes(first, boundary, small), (0, 0))
        self.assertEqual(self.resumes(first, small, boundary), (0, 0))  # by time, not by line
        later = other(700) + request(705, "p3", 0, 0, 3020, 10)  # counted: against p2's prompt
        self.assertEqual(self.resumes(first, boundary, small, later), (0, 1))
        # A compaction before the previous request, or after this one, hides nothing.
        self.assertEqual(self.resumes(other(1, kind="system", subtype="compact_boundary"), first,
                                      other(700), request(705, "p2", 0, 10000, 10, 10),
                                      other(710, kind="system", subtype="compact_boundary")),
                         (1, 0))
        # Another `system` record is not a compaction.
        self.assertEqual(self.resumes(first, other(100, kind="system", subtype="informational"),
                                      small), (0, 1))

    def test_every_resume_of_an_agent_is_counted(self):
        self.assertEqual(self.resumes(
            other(0), request(1, "p1", 0, 0, 10000, 10),
            other(100), request(101, "p2", 0, 10000, 10, 10),
            other(500), request(501, "p3", 0, 0, 10020, 10),
            other(900), request(901, "p4", 0, 0, 10030, 10),
            other(905), request(906, "p5", 0, 10030, 10, 10),
            other(1000), request(1001, "p6", 0, 10040, 10, 10)), (2, 2))


class ExpectedModelTest(Fixture):
    """`AGENT=MODEL`: the model the strategy gave the agent. A request counted on a model that
    matches none of the expected names (as `usage.matches` says) ends the `model` field in
    `!=MODEL`; the line keeps its fields, and nothing else changes."""

    def test_a_match_leaves_the_line_as_it_was(self):
        for arg in ("a1=model-a", "a1=MODEL-A", "a1=model", "a1=other,model-a"):
            self.assertEqual(lines(SESSION, arg), [IMPLEMENTER], arg)
        self.assertEqual(lines(SESSION, "b2=model-b", "orchestrator=model-a,model-c"),
                         [REVIEWER, ORCHESTRATOR])

    def test_another_model_is_marked_in_the_model_field(self):
        self.assertEqual(lines(SESSION, "a1=sonnet"),
                         [IMPLEMENTER.replace("| model-a |", "| model-a!=sonnet |")])
        self.assertEqual(lines(SESSION, "b2=Opus,Sonnet"),
                         [REVIEWER.replace("| model-b |", "| model-b!=opus,sonnet |")])
        for line in lines(SESSION, "a1=sonnet", "b2=x"):
            self.assertEqual(len(line.split(" | ")), 1 + len(usage.COLUMNS), line)

    def test_every_request_counts_not_only_the_last(self):
        # The orchestrator's last request ran on model-c, the three before it on model-a.
        self.assertEqual(lines(SESSION, "orchestrator=model-c"),
                         [ORCHESTRATOR.replace("| model-c |", "| model-c!=model-c |")])
        marker = os.path.join(self.tmp, "marker")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("R\n")
        os.utime(marker, (epoch(5015), epoch(5015)))  # only o4 counts: model-c
        self.assertEqual(lines(SESSION, "orchestrator=model-c", "--since", marker)[0].split(
            " | ")[3], "model-c")

    def test_a_suffix_a_date_and_inherit_are_no_mismatch(self):
        self.agent(self.new, "g7", "manager-plugin:implementer", (
            other(10), request(20, "q1", 1, 0, 100, 10, model="vendor-big-4-6")))
        plain = lines(SESSION, "g7")[0]
        for arg in ("g7=big[1m]", "g7=vendor-big-4-6[1m]", "g7=vendor-big-4-6-20260101",
                    "g7=inherit", "g7=Big", "g7=small,inherit", "g7=big-4-6"):
            self.assertEqual(lines(SESSION, arg), [plain], arg)
        self.assertEqual(lines(SESSION, "g7=small[1m]"),
                         [plain.replace("| vendor-big-4-6 |", "| vendor-big-4-6!=small |")])
        self.assertEqual(lines(SESSION, "g7=vendor-big-4-5-20250101"), [plain.replace(
            "| vendor-big-4-6 |", "| vendor-big-4-6!=vendor-big-4-5 |")])
        self.agent(self.new, "h8", None, (request(5, "q2", 1, 0, 1, 1,
                                                  model="vendor-big-4-6-20260101[1m]"),))
        self.assertNotIn("!=", lines(SESSION, "h8=vendor-big-4-6")[0])

    def test_a_versioned_name_must_end_the_id(self):
        self.agent(self.new, "g7", None, (request(5, "q1", 1, 0, 1, 1, model="vendor-big-4-6"),))
        self.assertIn("| vendor-big-4-6!=big-4 |", lines(SESSION, "g7=big-4")[0])
        self.agent(self.new, "h8", None, (request(5, "q2", 1, 0, 1, 1,
                                                  model="prov.vendor-big-4-6@20260101"),))
        self.assertNotIn("!=", lines(SESSION, "h8=vendor-big-4-6")[0])
        self.assertNotIn("!=", lines(SESSION, "h8=big")[0])
        self.assertIn("!=small |", lines(SESSION, "h8=small")[0])  # an alias of another family
        self.assertIn("!=g-4-6 |", lines(SESSION, "g7=g-4-6")[0])  # only on a `-` boundary

    def test_a_dotted_version_is_not_a_provider_prefix(self):
        self.agent(self.new, "g7", None, (request(5, "q1", 1, 0, 1, 1,
                                                  model="vendor-small-4.6"),))
        self.assertIn("!=big-4.6 |", lines(SESSION, "g7=big-4.6")[0])
        self.agent(self.new, "h8", None, (request(5, "q2", 1, 0, 1, 1,
                                                  model="prov.vendor-big-4.6@20260101"),))
        self.assertNotIn("!=", lines(SESSION, "h8=vendor-big-4.6")[0])
        self.assertNotIn("!=", lines(SESSION, "h8=big-4.6")[0])

    def test_a_bare_version_is_marked(self):
        """A name with no letters (`4-6`, `4.6`) names no family: it is marked, never a pass."""
        self.agent(self.new, "g7", None, (request(5, "q1", 1, 0, 1, 1,
                                                  model="vendor-small-4-6"),))
        for name in ("4-6", "6", "4.6", "-4-6"):
            self.assertIn("!=" + name + " |", lines(SESSION, "g7=" + name)[0], name)
        self.assertNotIn("!=", lines(SESSION, "g7=4-6,small")[0])  # another name still matches

    def test_a_trailing_provider_suffix_is_marked(self):
        # A false mark is the safe side: `-v1:0` after the version never passes.
        self.agent(self.new, "g7", None, (request(5, "q1", 1, 0, 1, 1,
                                                  model="vendor-big-4-6-v1:0"),))
        self.assertIn("!=vendor-big-4-6 |", lines(SESSION, "g7=vendor-big-4-6")[0])

    def test_what_is_unknown_is_never_marked(self):
        self.assertEqual(lines(SESSION, "zz=sonnet"), ["usage | zz | unknown" + UNKNOWN])
        self.assertEqual(lines("no-such-session", "orchestrator=sonnet"),
                         ["usage | orchestrator | main" + UNKNOWN])
        self.assertEqual(lines(SESSION, "a1"), [IMPLEMENTER])  # no `=`: no model named

    def test_names_that_are_empty_once_normalised_are_marked(self):
        """`=` with every name empty after `family` (`.`, `[1m]`, a date, `,`) names no model: the
        line is marked `!=unknown`, never left unchecked; `inherit` still turns the check off, and
        one real name among empty ones is checked as usual."""
        marked = [IMPLEMENTER.replace("| model-a |", "| model-a!=unknown |")]
        for arg in ("a1=", "a1=,", "a1=.", "a1=[1m]", "a1=-20260101", "a1=@20260101",
                    "a1=.,[1m],-20260101"):
            self.assertEqual(usage.expect(arg), ("a1", ("",)), arg)
            self.assertEqual(lines(SESSION, arg), marked, arg)
        for arg in ("a1=inherit", "a1=,inherit", "a1=[1m],model-a", "a1=model-a,"):
            self.assertEqual(lines(SESSION, arg), [IMPLEMENTER], arg)
        self.assertEqual(lines(SESSION, "a1=,sonnet"),
                         [IMPLEMENTER.replace("| model-a |", "| model-a!=sonnet |")])
        self.assertEqual(lines(SESSION, "zz=,"), ["usage | zz | unknown" + UNKNOWN])

    def test_a_name_with_a_model_is_still_never_a_path(self):
        self.assertEqual(lines(SESSION, "../a1=model-a", "a*=x"),
                         ["usage | .._a1 | unknown" + UNKNOWN, "usage | a_ | unknown" + UNKNOWN])
        self.assertEqual(lines(SESSION, "a1=x|y z"),
                         [IMPLEMENTER.replace("| model-a |", "| model-a!=x_y_z |")])

    def test_the_command_takes_the_models(self):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config)
        p = subprocess.run([sys.executable, "-I", "-B", SCRIPT, SESSION, "a1=sonnet", "b2=model-b"],
                           capture_output=True, env=env, cwd=self.tmp)
        self.assertEqual((p.returncode, p.stderr.decode()), (0, ""))
        self.assertEqual(p.stdout.decode("ascii").splitlines(),
                         [IMPLEMENTER.replace("| model-a |", "| model-a!=sonnet |"), REVIEWER])


def call(at, key, tool="Bash", given=None):
    """An assistant record holding one tool call."""
    return [{"type": "assistant", "timestamp": stamp(at), "message": {
        "id": "msg-" + key, "role": "assistant", "content": [
            {"type": "tool_use", "id": key, "name": tool,
             "input": given if given is not None else {"command": "make test"}}]}}]


def outcome(at, key, error=True):
    """The tool result of the call `key`, an error or not."""
    part = {"type": "tool_result", "tool_use_id": key, "content": "the secret output"}
    if error is not None:
        part["is_error"] = error
    return other(at, message={"role": "user", "content": [part]})


def failing(at, key, tool="Bash", given=None, error=True):
    return call(at, key, tool, given) + outcome(at + 1, key, error)


class StreakTest(Fixture):
    """`--streaks`: runs of 3 or more identical tool calls in a row, each ending in an error."""

    def streak(self, *groups, name="s1"):
        self.agent(self.new, name, "manager-plugin:worker", groups)
        return [line for line in lines(SESSION, name, "--streaks")
                if line.startswith("streaks ")]

    def test_off_by_default_the_lines_are_unchanged(self):
        self.assertEqual(lines(SESSION), [ORCHESTRATOR, REVIEWER, IMPLEMENTER, UNTIMED])
        self.assertEqual(lines(SESSION, "--streaks"), [
            ORCHESTRATOR, "streaks | orchestrator | 0 | 0 | none",
            "errors | orchestrator | 0 | 0 | 0 | 0",
            REVIEWER, "streaks | b2 | 0 | 0 | none", "errors | b2 | 0 | 0 | 0 | 0",
            IMPLEMENTER, "streaks | a1 | 0 | 0 | none", "errors | a1 | 0 | 0 | 0 | 0",
            UNTIMED, "streaks | c3 | 0 | 0 | none", "errors | c3 | 0 | 0 | 0 | 0"])
        self.assertEqual(lines(SESSION, "zz", "--streaks"),
                         ["usage | zz | unknown" + UNKNOWN, "streaks | zz | unknown | unknown | "
                                                            "unknown",
                          "errors | zz | unknown | unknown | unknown | unknown"])

    def test_three_identical_failures_are_a_streak(self):
        self.assertEqual(self.streak(failing(10, "t1"), failing(20, "t2"), failing(30, "t3")),
                         ["streaks | s1 | 1 | 3 | Bash"])
        self.assertEqual(self.streak(failing(10, "t1"), failing(20, "t2"), name="s2"),
                         ["streaks | s2 | 0 | 0 | none"])

    def test_count_and_longest(self):
        grep = {"pattern": "x", "path": "/somewhere/secret"}
        out = self.streak(
            failing(10, "t1"), failing(20, "t2"), failing(30, "t3"),
            failing(40, "t4", error=False),  # a success ends the run
            failing(50, "g1", "Grep", grep), failing(60, "g2", "Grep", grep),
            failing(70, "g3", "Grep", grep), failing(80, "g4", "Grep", grep),
            failing(90, "t5"))  # another call ends it too
        self.assertEqual(out, ["streaks | s1 | 2 | 4 | Grep"])
        self.assertNotIn("secret", "".join(out))

    def test_what_breaks_a_run(self):
        for label, middle in (
                ("another input", failing(25, "x", given={"command": "make lint"})),
                ("another tool", failing(25, "x", "Read", {"command": "make test"})),
                ("no is_error", failing(25, "x", error=None)),
                ("is_error false", failing(25, "x", error=False)),
                ("no result", call(25, "x"))):
            out = self.streak(failing(10, "t1"), failing(20, "t2"), middle, failing(30, "t3"),
                              failing(40, "t4"), name="b" + str(len(label)))
            self.assertEqual(out, ["streaks | b%d | 0 | 0 | none" % len(label)], label)

    def test_the_input_is_compared_whatever_its_key_order(self):
        one, two = {"a": 1, "b": [1, 2]}, {"b": [1, 2], "a": 1}
        self.assertEqual(self.streak(failing(10, "t1", "Edit", one), failing(20, "t2", "Edit", two),
                                     failing(30, "t3", "Edit", one)),
                         ["streaks | s1 | 1 | 3 | Edit"])

    def test_an_id_that_is_not_a_string_is_its_own_call(self):
        odd = failing(5, "o1")
        odd[0]["message"]["content"][0]["id"] = ["not", "a", "string"]
        nameless = call(6, "o2")
        nameless[0]["message"]["content"][0]["id"] = {"a": 1}
        self.assertEqual(self.streak(odd, nameless, failing(10, "t1"), failing(20, "t2"),
                                     failing(30, "t3")),
                         ["streaks | s1 | 1 | 3 | Bash"])

    def test_since_bounds_them(self):
        self.agent(self.new, "s1", None, (failing(10, "t1"), failing(20, "t2"),
                                          failing(30, "t3"), failing(40, "t4")))
        for since, expected in ((stamp(0), "1 | 4 | Bash"), (stamp(15), "1 | 3 | Bash"),
                                (stamp(25), "0 | 0 | none")):
            self.assertEqual(lines(SESSION, "s1", "--streaks", "--since", since)[1],
                             "streaks | s1 | " + expected, since)


def used(at, key, tool, given, content="", error=None):
    """A tool call and its result, the result's content as given (a text or a list of parts)."""
    part = {"type": "tool_result", "tool_use_id": key, "content": content}
    if error is not None:
        part["is_error"] = error
    return call(at, key, tool, given) + other(at + 1, message={"role": "user", "content": [part]})


def bash(at, key, command, content=""):
    return used(at, key, "Bash", {"command": command}, content)


def reading(at, key, path, content="", error=None, **span):
    return used(at, key, "Read", dict({"file_path": path}, **span), content, error)


class ToolsTest(Fixture):
    """`--tools`: calls, result characters and errors by tool; re-reads; code-map use."""

    def tools(self, *groups, name="t1", kind="tools"):
        self.agent(self.new, name, "manager-plugin:worker", groups)
        return [line for line in lines(SESSION, name, "--tools")
                if line.startswith(kind + " ")]

    def test_off_by_default_the_lines_are_unchanged(self):
        self.assertEqual(lines(SESSION), [ORCHESTRATOR, REVIEWER, IMPLEMENTER, UNTIMED])
        self.assertEqual(lines(SESSION, "--tools"), [
            ORCHESTRATOR, "reads | orchestrator | 0 | 0 | 0 | 0 | 0",
            "map | orchestrator | 0 | 0 | 0",
            REVIEWER, "reads | b2 | 0 | 0 | 0 | 0 | 0", "map | b2 | 0 | 0 | 0",
            IMPLEMENTER, "reads | a1 | 0 | 0 | 0 | 0 | 0", "map | a1 | 0 | 0 | 0",
            UNTIMED, "reads | c3 | 0 | 0 | 0 | 0 | 0", "map | c3 | 0 | 0 | 0"])

    def test_a_transcript_that_cannot_be_read_is_unknown(self):
        self.assertEqual(lines(SESSION, "zz", "--tools"), [
            "usage | zz | unknown" + UNKNOWN,
            "tools | zz | unknown | unknown | unknown | unknown | unknown",
            "reads | zz | unknown | unknown | unknown | unknown | unknown",
            "map | zz | unknown | unknown | unknown"])

    def test_both_flags_streaks_first(self):
        self.agent(self.new, "t1", None, (failing(10, "x1"), failing(20, "x2"),
                                          failing(30, "x3")))
        self.assertEqual(lines(SESSION, "t1", "--tools", "--streaks")[1:], [
            "streaks | t1 | 1 | 3 | Bash", "errors | t1 | 3 | 1 | 2 | 0",
            "tools | t1 | Bash | 3 | 51 | 3 | 0", "reads | t1 | 0 | 0 | 0 | 0 | 0",
            "map | t1 | 0 | 0 | 0"])

    def test_calls_chars_errors_most_chars_first(self):
        out = self.tools(
            reading(10, "r1", "/secret/a.py", "x" * 40),
            reading(20, "r2", "/secret/b.py", [{"type": "text", "text": "y" * 30},
                                               {"type": "image", "source": {"data": "z" * 999}},
                                               {"type": "text", "text": "y" * 5}]),
            bash(30, "b1", "make secret", "o" * 100),
            used(40, "g1", "Grep", {"pattern": "secret"}, "no matches", error=True),
            used(50, "g2", "Grep", {"pattern": "secret"}, "abc"),
            used(60, "w1", "Write", {"file_path": "/secret/c.py"}, "ok"),
            used(70, "e1", "Edit", {"file_path": "/secret/c.py"}, "ok"),
            call(80, "n1", "Glob", {"pattern": "*"}))  # no result: a call, no characters
        self.assertEqual(out, ["tools | t1 | Bash | 1 | 100 | 0 | 0",
                               "tools | t1 | Read | 2 | 75 | 0 | 0",
                               "tools | t1 | Grep | 2 | 13 | 1 | 0",
                               "tools | t1 | Edit | 1 | 2 | 0 | 0",
                               "tools | t1 | Write | 1 | 2 | 0 | 0",
                               "tools | t1 | Glob | 1 | 0 | 0 | 0"])
        self.assertNotIn("secret", "".join(lines(SESSION, "t1", "--tools")))

    def test_a_call_in_two_files_counts_once(self):
        both = reading(10, "r1", "/a.py", "x" * 7)
        self.agent(self.old, "t1", None, (both,))
        self.assertEqual(self.tools(both), ["tools | t1 | Read | 1 | 7 | 0 | 0"])

    def test_re_reads_unchanged(self):
        out = self.tools(
            reading(10, "r1", "/a.py"), reading(20, "r2", "/a.py"),  # a re-read
            reading(30, "r3", "/a.py", offset=10, limit=20),  # another range: no re-read
            reading(40, "r4", "/a.py", offset=10, limit=20),  # the same range: a re-read
            reading(50, "r5", "/b.py", error=True),  # failed: what follows is no re-read
            reading(60, "r6", "/b.py"),
            kind="reads")
        self.assertEqual(out, ["reads | t1 | 6 | 2 | 2 | 0 | 0"])

    def test_an_edit_between_two_reads(self):
        for tool, key in (("Edit", "file_path"), ("Write", "file_path"),
                          ("NotebookEdit", "notebook_path"), ("MultiEdit", "file_path")):
            name = "e" + str(len(tool))
            out = self.tools(reading(10, "r1", "/a.py"), reading(15, "r2", "/b.py"),
                             used(20, "e1", tool, {key: "/a.py"}),
                             reading(30, "r3", "/a.py"), reading(40, "r4", "/b.py"),
                             reading(50, "r5", "/a.py"), name=name, kind="reads")
            self.assertEqual(out, ["reads | %s | 5 | 2 | 2 | 0 | 0" % name], tool)

    def test_map_queries_other_map_calls_and_searches(self):
        out = self.tools(
            bash(10, "b1", "python3 /x/code-map/scripts/codemap.py query 'run loop' --budget 9"),
            bash(11, "b2", "cd /repo && python3 /x/codemap.py --root . mentions foo"),
            bash(12, "b3", "python3 /x/codemap.py build"),
            bash(13, "b4", "python3 /x/codemap.py"),  # no action: another map call
            bash(14, "b5", "grep -rn secret src"),
            bash(15, "b6", "cd /repo && LC_ALL=C rg secret"),
            bash(16, "b7", "timeout 120 find . -name '*.py'"),
            bash(17, "b8", "git grep -n secret"),
            bash(18, "b9", "make test | grep FAIL"),  # not the first command: no search
            bash(19, "b10", "echo 'unclosed"),
            bash(20, "b11", "git log --grep secret"),
            used(21, "g1", "Grep", {"pattern": "x"}), used(22, "g2", "Glob", {"pattern": "*"}),
            kind="map")
        self.assertEqual(out, ["map | t1 | 2 | 2 | 6"])

    def test_calls_is_another_map_call(self):
        out = self.tools(bash(10, "b1", "python3 /x/codemap.py calls helper --all"), kind="map")
        self.assertEqual(out, ["map | t1 | 0 | 1 | 0"])

    def test_timeout_options_with_a_value_word(self):
        out = self.tools(
            bash(10, "b1", "timeout -s KILL 120 grep -rn x ."),
            bash(11, "b2", "timeout -k 5 120 rg x"),
            bash(12, "b3", "timeout --signal KILL 60 find . -name x"),
            bash(13, "b4", "timeout --kill-after 5 --signal=TERM 60 git grep x"),
            bash(14, "b5", "timeout -sKILL --preserve-status 9 grep x f"),
            bash(15, "b6", "timeout -k 5 120 make test"),  # not a search
            kind="map")
        self.assertEqual(out, ["map | t1 | 0 | 0 | 5"])

    def test_since_bounds_them(self):
        self.agent(self.new, "t1", None, (
            reading(10, "r1", "/a.py", "abc"), reading(20, "r2", "/a.py", "abc"),
            bash(30, "b1", "rg x", "12345")))
        for since, expected in (
                (stamp(0), ["tools | t1 | Read | 2 | 6 | 0 | 0",
                            "tools | t1 | Bash | 1 | 5 | 0 | 0",
                            "reads | t1 | 2 | 1 | 1 | 0 | 0", "map | t1 | 0 | 0 | 1"]),
                (stamp(15), ["tools | t1 | Bash | 1 | 5 | 0 | 0",
                             "tools | t1 | Read | 1 | 3 | 0 | 0",
                             "reads | t1 | 1 | 1 | 0 | 0 | 0", "map | t1 | 0 | 0 | 1"]),
                (stamp(31), [  # only b1's result: not counted
                 "reads | t1 | 0 | 0 | 0 | 0 | 0", "map | t1 | 0 | 0 | 0"])):
            self.assertEqual(lines(SESSION, "t1", "--tools", "--since", since)[1:], expected,
                             since)


def ask(at, key, prompt, output, *uses, cached=0):
    """A request of `prompt` input tokens (`cached` of them read from the cache) whose one
    record holds the tool calls `uses`: (id, tool, input)."""
    record = request(at, key, prompt - cached, cached, 0, output)[0]
    record["message"]["content"] = [{"type": "tool_use", "id": i, "name": t, "input": g}
                                    for i, t, g in uses]
    return [record]


def reply(at, key, content="", error=None, uuid=None):
    """The tool result of the call `key`, in a record with `uuid`."""
    part = {"type": "tool_result", "tool_use_id": key, "content": content}
    if error is not None:
        part["is_error"] = error
    extra = {"uuid": uuid} if uuid else {}
    return other(at, message={"role": "user", "content": [part]}, **extra)


def boundary(at, *preserved):
    record = other(at, kind="system", subtype="compact_boundary")
    if preserved:
        record[0]["compactMetadata"] = {"preservedMessages": {"uuids": list(preserved)}}
    return record


class MeasureTest(Fixture):
    """Plugin 0.9.24: carried characters, Bash reads, `--prefix`, `--after-green`, `errors`."""

    def out(self, *groups, flag="--tools", kind="tools", name="m1", extra=()):
        self.agent(self.new, name, "manager-plugin:worker", groups)
        return [line for line in lines(SESSION, name, flag, *extra)
                if line.startswith(kind + " ")]

    def test_a_result_is_carried_by_every_later_request(self):
        out = self.out(
            other(0), ask(1, "q1", 100, 5, ("r1", "Read", {"file_path": "/s/a.py"})),
            reply(2, "r1", "x" * 100), ask(3, "q2", 200, 5, ("b1", "Bash", {"command": "ls"})),
            reply(4, "b1", "y" * 30), ask(5, "q3", 300, 5), ask(6, "q4", 300, 5),
            ask(7, "q5", 300, 5), ask(8, "q6", 300, 5), ask(9, "q7", 300, 5))
        # r1: 6 requests after it (q2-q7), 600; b1: 30 chars, 5 requests (q3-q7), 150.
        self.assertEqual(out, ["tools | m1 | Read | 1 | 100 | 0 | 600",
                               "tools | m1 | Bash | 1 | 30 | 0 | 150"])

    def test_sorted_by_carried_chars(self):
        out = self.out(
            other(0), ask(1, "q1", 100, 5, ("r1", "Read", {"file_path": "/s/a.py"})),
            reply(2, "r1", "x" * 30), ask(3, "q2", 200, 5),
            ask(4, "q3", 200, 5), ask(5, "q4", 200, 5, ("b1", "Bash", {"command": "ls"})),
            reply(6, "b1", "y" * 100), ask(7, "q5", 300, 5))
        self.assertEqual(out, ["tools | m1 | Read | 1 | 30 | 0 | 120",
                               "tools | m1 | Bash | 1 | 100 | 0 | 100"])

    def test_a_compaction_drops_what_it_does_not_preserve(self):
        groups = (other(0), ask(1, "q1", 100, 5, ("r1", "Read", {"file_path": "/s/a.py"}),
                                ("r2", "Read", {"file_path": "/s/b.py"})),
                  reply(2, "r1", "x" * 10, uuid="u-r1"), reply(2, "r2", "y" * 10, uuid="u-r2"),
                  ask(3, "q2", 200, 5), ask(4, "q3", 200, 5))
        later = (ask(11, "q4", 50, 5), ask(12, "q5", 60, 5))
        self.assertEqual(self.out(*groups, boundary(10), *later),
                         ["tools | m1 | Read | 2 | 20 | 0 | 40"])  # q2, q3 only
        self.assertEqual(self.out(*groups, boundary(10, "u-r2"), *later, name="m2"),
                         ["tools | m2 | Read | 2 | 20 | 0 | 60"])  # r2 also in q4, q5
        # The next compaction that does not list it ends it too.
        self.assertEqual(self.out(*groups, boundary(10, "u-r2"), *later, boundary(20),
                                  ask(21, "q6", 10, 5), name="m3"),
                         ["tools | m3 | Read | 2 | 20 | 0 | 60"])  # not in q6

    def test_bash_reads(self):
        commands = (("cat /s/a.py", True), ("cd /s && head -n 5 a.py", True),
                    ("sed -n '1,5p' a.py", True), ("sed -ne 1p a.py", True),
                    ("timeout 9 tail -20 x.log", True), ("nl a.py", True), ("bat a.py", True),
                    ("less a.py", True), ("more a.py", True), ("sed --quiet 1p a.py", True),
                    ("sed 's/a/b/' a.py", False), ("cat > /s/a.py <<'EOF'\nx\nEOF", False),
                    ("grep x a.py | cat", False), ("make test", False),
                    ("cat a.py | sed -n 1p", True))
        groups = [other(0)]
        for n, (command, _) in enumerate(commands):
            groups.append(bash(10 + 2 * n, "b%d" % n, command, "z" * (n + 1)))
        out = self.out(*groups, kind="reads")
        chars = sum(n + 1 for n, (_, shown) in enumerate(commands) if shown)
        self.assertEqual(out, ["reads | m1 | 0 | 0 | 0 | %d | %d" % (
            sum(shown for _, shown in commands), chars)])
        self.assertEqual(usage.bash_read("sed -i -n 1p a.py | cat"), True)
        self.assertEqual(usage.bash_read("echo x; cat a.py"), False)

    def test_prefix_share(self):
        groups = (other(0), request(1, "q1", 10, 0, 990, 5),  # 1,000: input + reads + writes
                  other(10), request(11, "q2", 2, 1000, 998, 5),
                  other(20), request(21, "q3", 0, 2000, 0, 5))
        self.assertEqual(self.out(*groups, flag="--prefix", kind="prefix"),
                         ["prefix | m1 | 1000 | 5000 | 20.0"])
        self.assertEqual(self.out(*groups, flag="--prefix", kind="prefix",
                                  extra=("--since", stamp(5))),
                         ["prefix | m1 | 2000 | 4000 | 50.0"])
        self.assertEqual(self.out(other(0), flag="--prefix", kind="prefix", name="m2"),
                         ["prefix | m2 | none"])
        self.assertEqual(lines(SESSION, "zz", "--prefix")[1],
                         "prefix | zz | unknown | unknown | unknown")
        # The total is the usage line's input + cache read + cache writes.
        line = lines(SESSION, "a1", "--prefix")
        fields = [int(v) for v in line[0].split(" | ")[5:9]]
        self.assertEqual(line[1].split(" | ")[3], str(sum(fields)))

    def green(self, *groups, name="m1", extra=()):
        return self.out(*groups, flag="--after-green", kind="after green", name=name,
                        extra=extra)

    TEST = ("t1", "Bash", {"command": "python3 -m unittest discover -s x -q"})

    def test_after_green(self):
        out = self.green(
            other(0), ask(1, "q1", 100, 10, ("e1", "Edit", {"file_path": "/s/a.py"})),
            reply(2, "e1", "ok"), ask(3, "q2", 200, 20, self.TEST), reply(4, "t1", "OK"),
            ask(5, "q3", 300, 30, ("r1", "Read", {"file_path": "/s/a.py"}),
                ("g1", "Grep", {"pattern": "x"})),
            reply(6, "r1", "x"), reply(6, "g1", "y"), ask(7, "q4", 400, 40))
        self.assertEqual(out, ["after green | m1 | 2 of 4 | 2 | 2 | 70 | 700"])

    def test_after_green_none(self):
        failed = (other(0), ask(1, "q1", 100, 10, ("e1", "Edit", {"file_path": "/s/a.py"})),
                  reply(2, "e1", "ok"), ask(3, "q2", 200, 20, self.TEST),
                  reply(4, "t1", "FAILED", error=True), ask(5, "q3", 300, 30))
        self.assertEqual(self.green(*failed), ["after green | m1 | none"])
        unchanged = (other(0), ask(3, "q2", 200, 20, self.TEST), reply(4, "t1", "OK"),
                     ask(5, "q3", 300, 30))
        self.assertEqual(self.green(*unchanged, name="m2"), ["after green | m2 | none"])
        edit_failed = (other(0), ask(1, "q1", 100, 10, ("e1", "Write", {"file_path": "/a"})),
                       reply(2, "e1", "no", error=True), ask(3, "q2", 200, 20, self.TEST),
                       reply(4, "t1", "OK"))
        self.assertEqual(self.green(*edit_failed, name="m3"), ["after green | m3 | none"])
        self.assertEqual(lines(SESSION, "zz", "--after-green")[1], "after green | zz | unknown")

    def test_green_then_edit_then_green(self):
        out = self.green(
            other(0), ask(1, "q1", 100, 10, ("e1", "Edit", {"file_path": "/s/a.py"})),
            reply(2, "e1", "ok"), ask(3, "q2", 200, 20, self.TEST), reply(4, "t1", "OK"),
            ask(5, "q3", 300, 30, ("e2", "MultiEdit", {"file_path": "/s/a.py"})),
            reply(6, "e2", "ok"),
            ask(7, "q4", 400, 40, ("t2", "Bash", {"command": "cd /r && npm run test"})),
            reply(8, "t2", "ok"), ask(9, "q5", 500, 50))
        self.assertEqual(out, ["after green | m1 | 4 of 5 | 1 | 0 | 50 | 500"])

    def test_green_by_a_log_and_its_status(self):
        logged = ("t1", "Bash", {"command": "python3 run.py > /tmp/x.log 2>&1; echo $?"})
        for status, expected in (("1", "none"), ("0", "2 of 3 | 1 | 0 | 30 | 300")):
            name = "l" + status
            out = self.green(
                other(0), ask(1, "q1", 100, 10, ("e1", "Edit", {"file_path": "/s/a.py"})),
                reply(2, "e1", "ok"), ask(3, "q2", 200, 20, logged),
                reply(4, "t1", status + "\n\n"), ask(5, "q3", 300, 30), name=name)
            self.assertEqual(out, ["after green | %s | %s" % (name, expected)], status)
        for command in ("pytest -q", "go test ./...", "cargo test", "make check", "ctest",
                        "mvn test", "gradle test", "yarn test", "pnpm test", "npm test",
                        "make test"):
            self.assertTrue(usage.TESTS.search(command), command)
        for command in ("make", "npm install", "echo test", "cat pytest.ini.bak"):
            self.assertFalse(usage.TESTS.search(command), command)

    def errors(self, *groups, name="m1", extra=()):
        return self.out(*groups, flag="--streaks", kind="errors", name=name, extra=extra)

    def test_error_signatures(self):
        def fail(at, key, tool, said):
            return ask(at, "q" + key, 100, 5, (key, tool, {"command": key})) \
                + reply(at + 1, key, said, error=True)
        out = self.errors(
            other(0),
            fail(10, "a", "Bash", "Error: /s/a.py line 12 not found"),
            fail(20, "b", "Bash", "Error: /x/y/b.py line 99 not found\nmore"),  # a repeat
            fail(30, "c", "Read", "File 'abc' missing"),
            fail(40, "d", "Bash", "Permission denied"),
            fail(50, "e", "Read", 'File "def" missing'),  # a repeat, not consecutive
            fail(60, "f", "Bash", "id deadbeef12 failed"),
            fail(70, "g", "Bash", "id 0123abcd99 failed"),  # a repeat
            fail(80, "h", "Grep", "Error: /s/a.py line 12 not found"),  # another tool
            ask(90, "qz", 100, 5))
        # Requests after the first repeat's result (at 21): qc ... qh and qz.
        self.assertEqual(out, ["errors | m1 | 8 | 5 | 3 | 7"])
        self.assertNotIn("secret", " ".join(lines(SESSION, "m1", "--streaks")))
        self.assertEqual(self.errors(other(0), fail(10, "a", "Bash", "x"),
                                     fail(20, "b", "Bash", "y"), name="m2"),
                         ["errors | m2 | 2 | 2 | 0 | 0"])
        self.assertEqual(usage.signature("Bash", "at 0x1f2e3d4c: 'q' in C:\\x\\y.py, 42"),
                         ("Bash", "at H: Q in P, N"))

    def test_since_bounds_them(self):
        groups = (other(0), ask(1, "q1", 100, 10, ("e1", "Edit", {"file_path": "/s/a.py"})),
                  reply(2, "e1", "boom", error=True),
                  ask(3, "q2", 200, 20, ("e2", "Edit", {"file_path": "/s/a.py"})),
                  reply(4, "e2", "boom", error=True),
                  ask(5, "q3", 300, 30, ("e3", "Edit", {"file_path": "/s/a.py"})),
                  reply(6, "e3", "ok"), ask(7, "q4", 400, 40, self.TEST), reply(8, "t1", "OK"),
                  ask(9, "q5", 500, 50))
        self.agent(self.new, "m1", None, groups)
        flags = ("--streaks", "--tools", "--prefix", "--after-green")
        self.assertEqual(lines(SESSION, "m1", *flags)[1:], [
            "streaks | m1 | 0 | 0 | none", "errors | m1 | 2 | 1 | 1 | 3",
            "tools | m1 | Edit | 3 | 10 | 2 | 32", "tools | m1 | Bash | 1 | 2 | 0 | 2",
            "reads | m1 | 0 | 0 | 0 | 0 | 0", "map | m1 | 0 | 0 | 0",
            "prefix | m1 | 100 | 1500 | 6.7", "after green | m1 | 4 of 5 | 1 | 0 | 50 | 500"])
        self.assertEqual(lines(SESSION, "m1", *flags, "--since", stamp(3))[1:], [
            "streaks | m1 | 0 | 0 | none", "errors | m1 | 1 | 1 | 0 | 0",
            "tools | m1 | Edit | 2 | 6 | 1 | 16", "tools | m1 | Bash | 1 | 2 | 0 | 2",
            "reads | m1 | 0 | 0 | 0 | 0 | 0", "map | m1 | 0 | 0 | 0",
            "prefix | m1 | 200 | 1400 | 14.3", "after green | m1 | 3 of 4 | 1 | 0 | 50 | 500"])

    def test_unknown_transcript_all_flags(self):
        self.assertEqual(lines(SESSION, "zz", "--streaks", "--tools", "--prefix",
                               "--after-green"), [
            "usage | zz | unknown" + UNKNOWN,
            "streaks | zz | unknown | unknown | unknown",
            "errors | zz | unknown | unknown | unknown | unknown",
            "tools | zz | unknown | unknown | unknown | unknown | unknown",
            "reads | zz | unknown | unknown | unknown | unknown | unknown",
            "map | zz | unknown | unknown | unknown",
            "prefix | zz | unknown | unknown | unknown", "after green | zz | unknown"])

    def test_without_the_flags_the_lines_are_unchanged(self):
        self.agent(self.new, "m1", None, (other(0), ask(1, "q1", 100, 10, self.TEST),
                                          reply(2, "t1", "OK")))
        self.assertEqual(lines(SESSION), [ORCHESTRATOR,
                                          "usage | m1 | unknown | model-a | 1 | 100 | 0 | 0 | "
                                          "0 | 10 | 110 | 0 | 0 | 2", REVIEWER, IMPLEMENTER,
                                          UNTIMED])
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config)
        p = subprocess.run([sys.executable, "-I", "-B", SCRIPT, SESSION, "a1", "--prefix",
                            "--after-green"], capture_output=True, env=env, cwd=self.tmp)
        self.assertEqual((p.returncode, p.stderr), (0, b""))
        self.assertEqual(p.stdout.decode("ascii").splitlines()[0], IMPLEMENTER)


if __name__ == "__main__":
    unittest.main()
