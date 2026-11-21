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
import usage  # noqa: E402

SCRIPT = os.path.join(HERE, "usage.py")
SESSION = "0f3c9a1e-5b7d-4c2a-9e1f-0123456789ab"
UNKNOWN = " | unknown" * 11

# What the fixture below adds up to, by hand.
ORCHESTRATOR = "usage | orchestrator | main | model-c | 4 | 10 | 47000 | 400 | 35500 | 650 | " \
               "21352 | 1 | 1 | 5020"
REVIEWER = "usage | b2 | manager-plugin:reviewer | model-b | 2 | 5 | 7000 | 7500 | 0 | 1100 | " \
           "8402 | 0 | 0 | 32"
IMPLEMENTER = "usage | a1 | manager-plugin:implementer | model-a | 7 | 17 | 29250 | 24600 | 0 | " \
              "5680 | 3092 | 1 | 1 | 900"
UNTIMED = "usage | c3 | unknown | model-a | 1 | 5 | 0 | 800 | 0 | 20 | 825 | unknown | unknown | " \
          "unknown"


def stamp(seconds):
    moment = datetime.datetime(2026, 1, 1, 9, 0, 0) + datetime.timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def other(at, kind="user", **fields):
    """A record that is not a request: a prompt, a tool result, a system line."""
    record = dict({"type": kind, "message": {"role": "user", "content": "text"}}, **fields)
    if at is not None:
        record["timestamp"] = stamp(at)
    return [record]


def request(at, key, fresh, cached, written, output, hour=0, blocks=1, model="model-a",
            split=True):
    """One request as a transcript holds it: a record per content block, each with the request's
    message id and usage (here the earlier ones with the output still at 1)."""
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
        self.addCleanup(shutil.rmtree, self.tmp)
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
            other(400),  # a subagent returns after 398 s: the 1-hour cache is still there
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
            other(520),
            request(530, "r2", 2, 7000, 500, 900, blocks=3, model="model-b")))
        self.agent(self.new, "a1", "manager-plugin:implementer", (
            other(1000),
            request(1005, "m1", 3, 0, 9000, 100, blocks=2),
            other(1020),
            request(1025, "m2", 2, 9000, 300, 50),  # 19 s later: not a resume
            other(1220),
            request(1225, "m3", 2, 9300, 200, 400),  # 200 s later, the context read: warm
            other(1700),
            request(1705, "m4", 4, 0, 9950, 60, blocks=2),  # 480 s later, written again: cold
            request(1710, "m5", 2, 9950, 100, 5000),
            other(1800, kind="system", subtype="compact_boundary"),
            request(1805, "m6", 2, 1000, 2000, 30),  # 95 s later, a smaller prompt: a compaction
            request(1825, "m7", 2, 0, 3050, 40),  # nothing read, but 20 s later: not a resume
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
            with open(os.path.join(folder, "agent-%s.meta.json" % name), "w") as fh:
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
        self.assertIn('`<python> "${CLAUDE_SKILL_DIR}/scripts/usage.py" <session id> <agent>... '
                      '>> <file>`', " ".join(record.split()))
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


class ResumeTest(Fixture):
    """A resume: a request 60 s or more after the agent's previous one. Cold: under half of the
    previous prompt read from the cache. A smaller prompt than before: a compaction, not counted."""

    def resumes(self, *groups):
        path = self.write(self.tmp, "one.jsonl", groups)
        totals = usage.read([path])
        return totals["warm"], totals["cold"]

    def test_the_gap_is_taken_from_the_previous_requests_last_record(self):
        first = request(0, "p1", 0, 0, 10000, 10, blocks=3)  # its last record: at 2 s
        self.assertEqual(self.resumes(first, request(61, "p2", 0, 10000, 10, 10)), (0, 0))
        self.assertEqual(self.resumes(first, request(62, "p2", 0, 10000, 10, 10)), (1, 0))
        self.assertEqual(self.resumes(first, request(61, "p2", 0, 0, 10010, 10)), (0, 0))
        self.assertEqual(self.resumes(first, request(62, "p2", 0, 0, 10010, 10)), (0, 1))

    def test_cold_is_under_half_of_the_previous_prompt(self):
        first = request(0, "p1", 0, 0, 10000, 10)
        for cached, expected in ((10000, (1, 0)), (5000, (1, 0)), (4999, (0, 1)), (0, (0, 1))):
            again = request(600, "p2", 10, cached, 10000 - cached, 10)
            self.assertEqual(self.resumes(first, again), expected, cached)
        grown = request(600, "p2", 0, 10000, 30000, 10)  # a long tool result: all read, more new
        self.assertEqual(self.resumes(first, grown), (1, 0))

    def test_a_smaller_prompt_follows_a_compaction(self):
        first = request(0, "p1", 0, 0, 10000, 10)
        self.assertEqual(self.resumes(first, request(600, "p2", 0, 2000, 7999, 10)), (0, 0))
        self.assertEqual(self.resumes(first, request(600, "p2", 0, 2000, 8000, 10)), (0, 1))

    def test_every_resume_of_an_agent_is_counted(self):
        self.assertEqual(self.resumes(
            request(0, "p1", 0, 0, 10000, 10), request(100, "p2", 0, 10000, 10, 10),
            request(500, "p3", 0, 0, 10020, 10), request(900, "p4", 0, 0, 10030, 10),
            request(905, "p5", 0, 10030, 10, 10), request(1000, "p6", 0, 10040, 10, 10)), (2, 2))


if __name__ == "__main__":
    unittest.main()
