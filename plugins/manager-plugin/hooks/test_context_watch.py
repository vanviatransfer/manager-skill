"""Tests for manager-context-watch.sh and context_watch.py, the PostToolUse hook on the Agent tool
that tells a manager run's orchestrator when its own context is over the budget:
python3 -m unittest discover -s <this folder>"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
from test_manager_compaction import MARKER, NOTES, SESSION, manager_texts  # noqa: E402
from test_prefer_plugin_agents import ENV, MANAGER, snapshot  # noqa: E402

HOOK = os.path.join(HERE, "manager-context-watch.sh")
SCRIPTS = os.path.join(MANAGER, "scripts")
sys.path.insert(0, SCRIPTS)
import context_watch  # noqa: E402

BUDGET = 200000


def request(key, fresh, cached, written, output, model="model-a", tool="Agent"):
    """A request's record: the orchestrator's message that calls the Agent tool (or another)."""
    return {"type": "assistant", "timestamp": "2026-01-01T09:00:00.000Z",
            "message": {"id": key, "model": model, "role": "assistant",
                        "content": [{"type": "tool_use", "id": "toolu_1", "name": tool}],
                        "usage": {"input_tokens": fresh, "cache_read_input_tokens": cached,
                                  "cache_creation_input_tokens": written,
                                  "output_tokens": output}}}


def sized(tokens, key="m1", tool="Agent"):
    """A request whose context is that many tokens."""
    return request(key, 3, tokens - 1203, 1000, 200, tool=tool)


RETURNED = {"type": "user", "timestamp": "2026-01-01T09:05:00.000Z",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "done"}]},
            "toolUseResult": {"agentId": "a1b2c3", "totalTokens": 999999,
                              "usage": {"input_tokens": 999999, "output_tokens": 999999}}}


class ContextWatchHookTest(unittest.TestCase):
    """manager-context-watch.sh: one context line when the session has a run marker and its last
    request held more than the budget; silent, exit 0 and nothing written everywhere else."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "my home")
        self.repo = os.path.join(self.tmp, "repo")
        self.path = os.path.join(self.home, ".claude", "projects", "-work", SESSION + ".jsonl")
        os.makedirs(os.path.dirname(self.path))
        os.makedirs(os.path.join(self.repo, ".git"))
        self.env = dict(ENV, HOME=self.home)
        for name in ("CLAUDE_PLUGIN_ROOT", "MANAGER_CONTEXT_BUDGET"):
            self.env.pop(name, None)

    def mark(self, session=SESSION):
        """Write the run marker where the manager skill says, for this session id."""
        path = MARKER.replace("~", self.home).replace("${CLAUDE_SESSION_ID}", session)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("R2026-01-01-0000\n")
        return path

    def transcript(self, *records, **kw):
        with open(kw.get("path", self.path), "w", encoding="utf-8", newline="\n") as fh:
            for record in records:
                fh.write(record if isinstance(record, str) else json.dumps(record) + "\n")

    def hook(self, raw=None, env=None, **fields):
        payload = {"session_id": SESSION, "transcript_path": self.path, "cwd": self.repo,
                   "permission_mode": "default", "hook_event_name": "PostToolUse",
                   "tool_name": "Agent", "tool_use_id": "toolu_1",
                   "tool_input": {"description": "a phase", "prompt": "Read and follow the brief.",
                                  "subagent_type": "manager-plugin:implementer"},
                   "tool_response": {"status": "completed", "agentId": "a1b2c3",
                                     "content": [{"type": "text", "text": "RESULT: READY"}],
                                     "totalTokens": 999999,
                                     "usage": {"input_tokens": 999999, "output_tokens": 999999}}}
        payload.update(fields)
        data = raw if raw is not None else json.dumps(payload)
        p = subprocess.run(["sh", HOOK], input=data if isinstance(data, bytes) else data.encode(),
                           capture_output=True, env=env or self.env, cwd=self.repo)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")

    def assert_silent(self, **kw):
        self.assertEqual(self.hook(**kw), (0, "", ""), kw)

    def line(self, **kw):
        """The one line the hook adds to the context."""
        code, out, err = self.hook(**kw)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("\n"), 1, out)
        output = json.loads(out)
        self.assertEqual(list(output), ["hookSpecificOutput"])
        self.assertEqual(sorted(output["hookSpecificOutput"]),
                         ["additionalContext", "hookEventName"])
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("\n", text)
        self.assertTrue(text.startswith("manager-plugin: this session's context is "), text)
        return text

    def test_at_or_below_the_budget_it_is_silent(self):
        self.mark()
        for tokens in (9000, BUDGET - 1, BUDGET):
            self.transcript(sized(tokens))
            self.assert_silent()

    def test_above_the_budget_it_adds_one_line(self):
        self.mark()
        self.transcript(sized(BUDGET + 1))
        text = self.line()
        self.assertTrue(text.startswith(
            "manager-plugin: this session's context is 200,001 tokens, over the manager run's "
            "budget of 200,000: make sure your notes file is current (never print the notes), "),
            text)
        self.assertEqual(NOTES, "~/.claude/manager-runs/notes/${CLAUDE_SESSION_ID}.md")
        self.assertIn("when you next stop for the owner, suggest once that they run `/compact` "
                      "before they answer.", text)
        self.assertNotIn("write every working-notes line", text)
        # A condition, never a statement: read as one, it ended a live run's notes.
        self.assertTrue(text.endswith(
            "(If no manager run is in progress any more, ignore this line and remove "
            "~/.claude/manager-runs/active/%s and ~/.claude/manager-runs/notes/%s.md.)"
            % (SESSION, SESSION)), text)
        self.assertNotIn("has ended", text)
        self.assertIn("working-notes line", " ".join(manager_texts().values()))
        self.assertLess(len(text), 500)
        pretty = json.dumps({"session_id": SESSION, "transcript_path": self.path}, indent=2)
        self.assertEqual(self.line(raw=pretty), text)
        self.transcript(request("m1", 12, 640000, 3500, 700))
        self.assertIn(" is 644,212 tokens, over ", self.line())

    def test_the_last_request_counts(self):
        self.mark()
        large, small = sized(BUDGET + 50000, "m1"), sized(30000, "m2")
        compacted = {"type": "system", "subtype": "compact_boundary",
                     "timestamp": "2026-01-01T09:10:00.000Z"}
        self.transcript(large, RETURNED, compacted, small)  # after a compaction: small again
        self.assert_silent()
        self.transcript(small, RETURNED, large)
        self.assertIn(" is 250,000 tokens, ", self.line())
        # What follows the request in the transcript is not a request: the subagent's return
        # (with its own usage), an attachment, an error message, a line that is not a record.
        after = (RETURNED, {"type": "attachment", "attachment": {"usage": 1}},
                 request("e1", 0, 0, 0, 0, model="<synthetic>"), "not json\n", '"usage"\n')
        self.transcript(small, large, *after)
        self.assertIn(" is 250,000 tokens, ", self.line())
        self.transcript(large, small, *after)
        self.assert_silent()

    def test_it_speaks_once_per_crossing(self):
        """Stateless: the line comes when the last request is over the budget and the request
        before it that called the Agent or Task tool (the hook's previous chance) was not."""
        self.mark()
        under, at, over = sized(BUDGET - 1, "m1"), sized(BUDGET, "m1"), sized(BUDGET + 1, "m1")
        now = sized(BUDGET + 9000, "m9")
        for before in (under, at, sized(9000, "m1", tool="Task")):  # crossing now
            self.transcript(before, RETURNED, now)
            self.assertIn(" is 209,000 tokens, ", self.line())
        self.transcript(over, RETURNED, now)  # already over at the previous return: silent
        self.assert_silent()
        self.transcript(sized(BUDGET + 5, "m1", tool="Task"), RETURNED, now)
        self.assert_silent()
        # Requests that call no subagent don't count: the hook never ran after them.
        tools = [sized(BUDGET + 100 * n, "b%d" % n, tool="Bash") for n in range(1, 4)]
        self.transcript(under, RETURNED, *tools, now)
        self.assertIn(" is 209,000 tokens, ", self.line())
        self.transcript(over, RETURNED, *tools, now)
        self.assert_silent()
        self.transcript(sized(9000, "b0", tool="Bash"), now)  # no earlier Agent call: as before
        self.assertIn(" is 209,000 tokens, ", self.line())
        self.transcript(now)  # no earlier request at all
        self.assertIn(" is 209,000 tokens, ", self.line())
        # A compaction brings the context under the budget; the next crossing speaks again.
        compacted = {"type": "system", "subtype": "compact_boundary"}
        self.transcript(over, compacted, sized(40000, "m2"), RETURNED, now)
        self.assertIn(" is 209,000 tokens, ", self.line())
        # One request, several records (one per content block, the last complete): the request
        # before it is another message id, not an earlier block of the same one.
        blocks = [request("m9", 3, 200, 100, 7), request("m9", 3, BUDGET, 1000, 200)]
        self.transcript(under, RETURNED, *blocks)
        self.assertIn(" is 201,203 tokens, ", self.line())
        self.transcript(over, RETURNED, *blocks)
        self.assert_silent()
        partial = request("m1", 3, BUDGET, 1000, 200)  # m1's last record: over
        self.transcript(request("m1", 0, 10, 0, 0), partial, RETURNED, now)
        self.assert_silent()
        # The previous Agent call before the end that is read: as without one.
        filler = json.dumps({"type": "attachment", "text": "x" * 4000}) + "\n"
        self.transcript(over, filler * 300, now)
        self.assertIn(" is 209,000 tokens, ", self.line())

    def test_a_compaction_bounds_the_scan(self):
        """Only the requests after the last `compact_boundary` record count: an Agent call from
        before it, under or over the budget, is no earlier chance in this context."""
        self.mark()
        now = sized(BUDGET + 9000, "m9")
        compacted = {"type": "system", "subtype": "compact_boundary",
                     "timestamp": "2026-01-01T09:10:00.000Z"}
        for before in (sized(BUDGET + 1, "m1"), sized(9000, "m1")):
            self.transcript(before, RETURNED, compacted, now)
            self.assertIn(" is 209,000 tokens, ", self.line())
            self.transcript(before, RETURNED, compacted, sized(BUDGET + 1, "m2"), RETURNED, now)
            self.assert_silent()  # over already at an Agent call after the compaction
            self.transcript(before, compacted, sized(9000, "m2", tool="Bash"), now)
            self.assertIn(" is 209,000 tokens, ", self.line())
        # Only the record itself bounds it: not the word in a tool result or a text field.
        quoted = dict(RETURNED, message={"role": "user", "content": [
            {"type": "tool_result",
             "content": '{"type": "system", "subtype": "compact_boundary"}'}]})
        self.transcript(sized(BUDGET + 1, "m1"), quoted, now)
        self.assert_silent()
        self.transcript(sized(BUDGET + 1, "m1"), compacted)  # no request since: silent
        self.assert_silent()

    def test_spawns_in_one_message_bring_the_line_once(self):
        """Several Agent calls in one request: one hook each; the line comes only at the hook of
        the request's first call, by the input's `tool_use_id`."""
        self.mark()
        def batch(key, tokens, ids, split):
            """One request's records: its calls in one record, or one record per call."""
            parts = [{"type": "tool_use", "id": i, "name": "Agent" if n else "Task"}
                     for n, i in enumerate(ids)]
            records = []
            for chunk in ([[p] for p in parts] if split else [parts]):
                record = sized(tokens, key)
                record["message"]["content"] = [{"type": "text", "text": "three phases"}] + chunk
                records.append(record)
            return records
        ids = ["toolu_a", "toolu_b", "toolu_c"]
        for split in (False, True):
            self.transcript(sized(9000, "m1"), RETURNED, *batch("m2", BUDGET + 1, ids, split))
            spoke = [i for i in ids if self.hook(tool_use_id=i)[1]]
            self.assertEqual(spoke, ["toolu_a"], split)
            # Ids that can't be placed: as before, the line comes.
            for call in (None, 7, "", "toolu_other"):
                self.assertIn(" is 200,001 tokens, ", self.line(tool_use_id=call))
            payload = {"session_id": SESSION, "transcript_path": self.path}
            self.assertIn(" is 200,001 tokens, ", self.line(raw=json.dumps(payload)))
        # A request whose calls carry no id: nothing to place, the line comes.
        record = sized(BUDGET + 1, "m2")
        record["message"]["content"] = [{"type": "tool_use", "name": "Agent"}]
        self.transcript(sized(9000, "m1"), record)
        self.assertIn(" is 200,001 tokens, ", self.line(tool_use_id="toolu_b"))
        # Another tool first in the message: the first Agent call is the one.
        record = sized(BUDGET + 1, "m2")
        record["message"]["content"] = [{"type": "tool_use", "id": "toolu_x", "name": "Bash"},
                                        {"type": "tool_use", "id": "toolu_b", "name": "Agent"},
                                        {"type": "tool_use", "id": "toolu_c", "name": "Agent"}]
        self.transcript(sized(9000, "m1"), record)
        self.assertIn(" is 200,001 tokens, ", self.line(tool_use_id="toolu_b"))
        self.assert_silent(tool_use_id="toolu_c")

    def test_the_notes_folder_is_no_marker(self):
        self.transcript(sized(BUDGET + 1))
        notes = NOTES.replace("~", self.home).replace("${CLAUDE_SESSION_ID}", SESSION)
        os.makedirs(os.path.dirname(notes))
        with open(notes, "w", encoding="utf-8") as fh:
            fh.write("Run R1: model strategy fixed\n")
        with open(os.path.join(os.path.dirname(notes), SESSION), "w", encoding="utf-8") as fh:
            fh.write("R1\n")
        self.assert_silent()
        os.makedirs(os.path.join(self.home, ".claude", "manager-runs", "active"))
        self.assert_silent()
        self.mark()
        self.assertIn(" is 200,001 tokens, ", self.line())

    def test_only_the_end_of_the_transcript_is_read(self):
        self.mark()
        filler = json.dumps({"type": "attachment", "text": "x" * 4000}) + "\n"
        self.transcript("not a record at all\n" * 150000, sized(BUDGET + 1), RETURNED)
        self.assertGreater(os.path.getsize(self.path), 2 << 20)
        self.assertIn(" is 200,001 tokens, ", self.line())
        self.transcript(sized(BUDGET + 1), filler * 300)  # the request: over 1 MiB before the end
        self.assertGreater(os.path.getsize(self.path), 1 << 20)
        self.assert_silent()
        self.transcript(sized(BUDGET + 1), filler * 200)
        self.assertIn(" is 200,001 tokens, ", self.line())

    def test_outside_a_manager_run_it_is_silent(self):
        self.transcript(sized(BUDGET + 1))
        self.assert_silent()  # no marker folder
        active = os.path.join(self.home, ".claude", "manager-runs", "active")
        os.makedirs(active)
        with open(os.path.join(self.home, ".claude", "manager-runs", "2026-01-01.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("a run record is not a marker\n")
        self.assert_silent()  # no marker
        other = self.mark("another-session")
        self.assert_silent()  # another session's run
        self.transcript(sized(BUDGET + 1), path=other + ".jsonl")
        self.assertIn("/active/another-session and "
                      "~/.claude/manager-runs/notes/another-session.md.)",
                      self.line(session_id="another-session", transcript_path=other + ".jsonl"))
        path = self.mark()
        self.assertIn("/notes/%s.md.)" % SESSION, self.line())
        os.remove(path)  # the run has ended
        self.assert_silent()
        os.makedirs(path)  # a folder is not a marker
        self.assert_silent()

    def test_without_any_marker_python_is_not_started(self):
        """The common path, any session that is no manager run: `sh` and `cat` only."""
        tools = os.path.join(self.tmp, "bin")
        os.makedirs(tools)
        for name in ("sh", "cat"):
            found = shutil.which(name)
            if not found or not hasattr(os, "symlink"):
                self.skipTest("needs sh, cat and symlinks")
            portability.symlink(self, found, os.path.join(tools, name))
        started = os.path.join(self.tmp, "started")
        for name in ("python3", "python", "py"):  # `py -3`: the launcher's own option
            with open(os.path.join(tools, name), "w", encoding="utf-8") as fh:
                fh.write('#!/bin/sh\necho %s >> "%s"\n%sexec "%s" "$@"\n'
                         % (name, started, "shift\n" if name == "py" else "", sys.executable))
            os.chmod(os.path.join(tools, name), 0o755)
        self.env["PATH"] = tools
        self.transcript(sized(BUDGET + 1))
        self.assert_silent()
        os.makedirs(os.path.join(self.home, ".claude", "manager-runs", "active"))
        self.assert_silent()
        self.assertFalse(os.path.exists(started))
        self.mark()
        self.assertIn(" is 200,001 tokens, ", self.line())
        with open(started, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "python3\n")
        # It finds Python as the other hooks do: python3, python, py -3; none: silent.
        for gone, expected in (("python3", "python3\npython\n"),
                               ("python", "python3\npython\npy\n")):
            os.remove(os.path.join(tools, gone))
            self.assertIn(" is 200,001 tokens, ", self.line())
            with open(started, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), expected)
        os.remove(os.path.join(tools, "py"))
        self.assert_silent()

    def test_a_missing_transcript_is_silent(self):
        self.mark()
        self.assert_silent()  # the file does not exist
        self.transcript()  # an empty one
        self.assert_silent()
        self.transcript(RETURNED, "not json\n", {"type": "user", "message": {
            "id": "u1", "usage": {"input_tokens": 999999}}})  # one without a request
        self.assert_silent()
        self.transcript(sized(BUDGET + 1))
        self.assertNotEqual(self.hook()[1], "")
        for path in (None, 0, 1, True, ["a list"], "", os.path.dirname(self.path),
                     os.path.join(self.tmp, "nowhere", "s.jsonl"), self.path + "\0"):
            self.assert_silent(transcript_path=path)
        payload = {"session_id": SESSION, "hook_event_name": "PostToolUse"}
        self.assert_silent(raw=json.dumps(payload))  # no path in the input
        # A number is no path: Python would read the open file that has it.
        markers, fd = os.path.dirname(self.mark()), os.open(self.path, os.O_RDONLY)
        try:
            payload["transcript_path"] = self.path
            self.assertIn(" is 200,001 tokens, ", context_watch.line(payload, markers))
            payload["transcript_path"] = fd
            self.assertIsNone(context_watch.line(payload, markers))
        finally:
            os.close(fd)

    def test_the_budget_can_be_set(self):
        self.mark()
        self.transcript(sized(150001))
        self.assert_silent()
        for value in ("150000", " 150000 ", "150_000"):
            self.env["MANAGER_CONTEXT_BUDGET"] = value
            self.assertIn(" is 150,001 tokens, over the manager run's budget of 150,000: ",
                          self.line())
        self.env["MANAGER_CONTEXT_BUDGET"] = "150001"
        self.assert_silent()
        self.transcript(sized(250000))
        self.env["MANAGER_CONTEXT_BUDGET"] = "400000"
        self.assert_silent()
        for value in ("", "0", "-5", "abc", "1.5", "2e5", "200k"):  # not a budget: the default
            self.env["MANAGER_CONTEXT_BUDGET"] = value
            self.assertIn(" is 250,000 tokens, over the manager run's budget of 200,000: ",
                          self.line(), value)
            self.transcript(sized(BUDGET))
            self.assert_silent()
            self.transcript(sized(250000))

    def test_a_subagents_own_tool_call_is_silent(self):
        self.mark()
        self.transcript(sized(BUDGET + 1))
        self.assert_silent(agent_id="a1b2c3", agent_type="manager-plugin:implementer")
        # Only the input's own field counts: not one inside the tool's input or response.
        for fields in ({"agent_id": None}, {"agent_id": ""},
                       {"tool_response": {"agent_id": "a1b2c3", "session_id": "another-session"}},
                       {"tool_input": {"prompt": 'keep "agent_id": "x", "session_id": "y"'}}):
            self.assertIn(" is 200,001 tokens, ", self.line(**fields))

    def test_errors_fail_open(self):
        self.mark()
        self.mark("x")
        self.transcript(sized(BUDGET + 1))
        self.assertNotEqual(self.hook()[1], "")
        for raw in ("not json", "", "[]", "{", "null", '"text"', '{"session_id": 7}',
                    '{"session_id": null}', '{"session_id": ""}', '{"session_id": "../active/x"}',
                    '{"session_id": "a b"}', '{"session_id": "x/../x"}', '{"session_id": "*"}',
                    b'\xff\xfe {"session_id": "\xff"}'):
            self.assertEqual(self.hook(raw=raw), (0, "", ""), raw)
        for session in (7, None, "", "../active/x", "x/../x", "*", ["x"], "no-run-here"):
            self.assert_silent(session_id=session)
        self.assert_silent(env={k: v for k, v in self.env.items() if k != "HOME"})
        self.assert_silent(env=dict(self.env, HOME=""))
        self.assert_silent(env=dict(self.env, HOME=os.path.join(self.tmp, "nowhere")))
        # Python finds usage.py beside the script, whatever the environment says.
        with open(os.path.join(self.tmp, "usage.py"), "w", encoding="utf-8") as fh:
            fh.write("raise SystemExit('not this one')\n")
        self.assertNotEqual(self.hook(env=dict(self.env, PYTHONPATH=self.tmp,
                                               PYTHONSAFEPATH="1"))[1], "")

    def test_nothing_is_written(self):
        self.mark()
        self.transcript(sized(BUDGET + 1))
        other = os.path.join(self.tmp, "small.jsonl")
        self.transcript(sized(9000), path=other)
        before = snapshot(self.tmp), sorted(os.listdir(HERE)), sorted(os.listdir(SCRIPTS))
        del self.env["PYTHONDONTWRITEBYTECODE"]  # the hook's own: no bytecode beside the scripts
        if not os.path.exists(os.path.join(SCRIPTS, "__pycache__")):
            self.addCleanup(shutil.rmtree, os.path.join(SCRIPTS, "__pycache__"), True)
        self.assertNotEqual(self.hook()[1], "")
        self.assert_silent(transcript_path=other)
        self.assert_silent(session_id="no-run-here")
        self.assert_silent(raw="not json")
        self.assert_silent(agent_id="a1")
        self.assertEqual((snapshot(self.tmp), sorted(os.listdir(HERE)),
                          sorted(os.listdir(SCRIPTS))), before)
        self.assertEqual(os.listdir(self.repo), [".git"])

    def test_hook_entry(self):
        with open(os.path.join(HERE, "hooks.json"), encoding="utf-8") as fh:
            entries = json.load(fh)["hooks"]["PostToolUse"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "Agent|Task")
        self.assertEqual(len(entries[0]["hooks"]), 1)
        entry = entries[0]["hooks"][0]
        self.assertEqual(entry["type"], "command")
        self.assertEqual(entry["command"],
                         'sh "${CLAUDE_PLUGIN_ROOT}/hooks/manager-context-watch.sh"')
        self.assertEqual(entry.get("onFailure"), "continue")
        self.assertLessEqual(entry["timeout"], 10)
        self.assertTrue(os.access(HOOK, os.X_OK))

    def test_the_hook_reads_the_marker_the_skill_writes(self):
        with open(os.path.join(MANAGER, "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("`%s`" % MARKER, fh.read())
        self.assertEqual(MARKER, "~/.claude/manager-runs/active/${CLAUDE_SESSION_ID}")
        with open(HOOK, encoding="utf-8") as fh:
            hook = fh.read()
        self.assertIn('runs="$HOME/.claude/manager-runs/active"\n', hook)
        self.assertIn("200,000 tokens", hook)
        self.assertIn("MANAGER_CONTEXT_BUDGET", hook)
        with open(os.path.join(SCRIPTS, "context_watch.py"), encoding="utf-8") as fh:
            script = fh.read()
        self.assertIn("\nBUDGET = %d\n" % BUDGET, script)
        self.assertIn("The budget is 200,000 tokens; the environment variable "
                      "`MANAGER_CONTEXT_BUDGET`", " ".join(script.split()))


if __name__ == "__main__":
    unittest.main()
