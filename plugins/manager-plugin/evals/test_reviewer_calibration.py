"""The reviewer-calibration suite (`reviewer-calibration/`), checked without a paid run:
python3 -m unittest discover -s <this folder>

- Every case is a valid `claude plugin eval` case (the format of `test_evals.py`), tagged
  `reviewer-calibration` only, with the same prompt, graders and answer-key shape; the mix is the
  one the suite promises (8 planted bugs over L1-L4, 2 guard cases, 4 decoys, 4 clean diffs, 2
  round-2 cases).
- Every scaffold builds the same two (round 2: three) commits every time, leaves the checkout on
  the candidate with a clean tree, refuses a folder that holds a repository and keeps its
  repository small; the base plan passes `plan.py check`; the commits the prompt names are the
  ones it builds; validation exits 0 at every candidate (the zero-tests case: with 0 tests run),
  so no planted bug is caught by the tests alone; each answer key's probe fails at a planted or
  unfixed candidate and passes at the others; each key's line range holds its marker text; no
  answer key reaches the workspace.
- score.py grades hand-written answers right (found, missed, false alarm, round 2, no verdict),
  reads a run's result and trace, and run.py builds the command with its defaults and a
  required cost ceiling.
Standard library only, Python 3.8+.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, "reviewer-calibration")
sys.path.insert(0, HERE)
sys.path.insert(0, SUITE)
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
import run as runner  # noqa: E402
import score  # noqa: E402
from test_evals import (CALIBRATION, INVARIANTS, PLAN_PY, README, case_folders, load,  # noqa: E402
                        problems, read)

KINDS = {"planted": 10, "decoy": 4, "clean": 4, "round2-fixed": 1, "round2-unfixed": 1}
LEVELS = {"L1": 2, "L2": 2, "L3": 2, "L4": 2, "guard": 2}
GRADERS = ("answer-relayed", "blind", "reviewer-dispatched", "verdict")
REFUSE = ("planted", "round2-unfixed")
DISPATCH = re.compile(r"Base SHA: ([0-9a-f]{40})   Candidate SHA: ([0-9a-f]{40})\n")
MAX_LINES = 150


def suite_cases():
    return [folder for folder in case_folders(skip=()) if folder.startswith(CALIBRATION + "/")]


def key_of(folder):
    with open(os.path.join(HERE, *folder.split("/"), "answer.json"), encoding="utf-8") as fh:
        return json.load(fh)


def build(folder, into):
    """The workspace of a case after its scaffold, run as the eval runner runs it."""
    work = os.path.join(into, "home", "cwd")
    os.makedirs(work)
    code, err = scaffold_run(folder, work)
    if code:
        raise AssertionError("%s: scaffold exit %d: %s" % (folder, code, err))
    return work


def scaffold_run(folder, work):
    home = os.path.dirname(work)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "USERPROFILE": home,
           "TERM": "dumb", "GIT_CONFIG_NOSYSTEM": "1"}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    script = os.path.join(HERE, *folder.split("/"), "scaffold.sh")
    done = subprocess.run([portability.bash(), script], cwd=work, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    return done.returncode, done.stderr.decode("utf-8", "replace")


def git(work, *args):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=os.path.dirname(work))
    done = subprocess.run(["git"] + list(args), cwd=work, env=env, capture_output=True)
    if done.returncode:
        raise AssertionError("git %s: %s" % (" ".join(args), done.stderr.decode()))
    return done.stdout.decode("utf-8").strip()


def python(work, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable] + list(args), cwd=work, env=env,
                          capture_output=True, timeout=120)


class CaseTest(unittest.TestCase):
    """The case files and answer keys, without a scaffold."""

    @classmethod
    def setUpClass(cls):
        cls.folders = suite_cases()
        cls.cases = {folder: load(folder) for folder in cls.folders}
        cls.keys = {folder: key_of(folder) for folder in cls.folders}

    def test_the_mix(self):
        kinds = [key["kind"] for key in self.keys.values()]
        self.assertEqual({kind: kinds.count(kind) for kind in set(kinds)}, KINDS)
        levels = [key["level"] for key in self.keys.values() if key["kind"] == "planted"]
        self.assertEqual({level: levels.count(level) for level in set(levels)}, LEVELS)
        self.assertTrue(all(key["level"] is None for key in self.keys.values()
                            if key["kind"] != "planted"))
        names = {folder.split("/")[-1] for folder in self.folders}
        self.assertLessEqual({"rc-weakened-test", "rc-zero-tests"}, names)

    def test_every_case_is_a_valid_case_of_this_suite_only(self):
        for folder, case in self.cases.items():
            with self.subTest(case=folder):
                self.assertEqual(problems(case), [])
                self.assertEqual(case["name"], folder.split("/")[-1])
                self.assertTrue(case["name"].startswith("rc-"))
                self.assertEqual(case["tags"], [CALIBRATION])
                self.assertNotIn(CALIBRATION, INVARIANTS)
                self.assertEqual((case["runs"], case["execution"]["model"]), (1, "sonnet"))
                self.assertEqual(case["context"], {"scaffold_script": "scaffold.sh"})
                self.assertEqual(sorted(case["execution"]["allowed_tools"]),
                                 sorted(["Agent", "Bash", "Read", "Glob", "Grep", "ToolSearch"]))
                self.assertFalse(os.path.isdir(os.path.join(HERE, *folder.split("/"), "mocks")))
        names = [case["name"] for case in self.cases.values()]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(sorted(set(f.split("/")[-1] for f in case_folders()) & set(names)), [],
                         "the invariant cases' tests must not take these in")

    def test_the_prompt_is_the_dispatch_and_tells_nothing(self):
        prompts = {}
        for folder, case in self.cases.items():
            prompt, key = case["execution"]["prompt"], self.keys[folder]
            with self.subTest(case=folder):
                self.assertEqual(len(DISPATCH.findall(prompt)), 1)
                self.assertIn("`manager-plugin:reviewer`", prompt)
                previous = re.findall(r"(?m)^ *Previous blockers: (B1\. .+)$", prompt)
                self.assertEqual(bool(previous), key["kind"].startswith("round2"))
                for word in ("VERDICT", "answer.json", "planted", "decoy", "calibration",
                             key["kind"]):
                    self.assertNotIn(word.lower(), prompt.lower())
                self.assertNotIn(case["description"].lower(), prompt.lower())
                prompts[folder] = DISPATCH.sub("", re.sub(r"(?m)^ *Previous blockers: .*\n", "",
                                                          prompt))
        self.assertEqual(len(set(prompts.values())), 1, "one prompt, apart from the commits")

    def test_the_graders(self):
        for folder, case in self.cases.items():
            graders = {grader["name"]: grader for grader in case["graders"]}
            candidate = DISPATCH.search(case["execution"]["prompt"]).group(2)
            refuse = self.keys[folder]["kind"] in REFUSE
            with self.subTest(case=folder):
                self.assertEqual(sorted(graders), sorted(GRADERS))
                self.assertEqual(graders["reviewer-dispatched"]["tool"], "Agent")
                self.assertTrue(graders["reviewer-dispatched"]["input_match"].endswith(
                    "Candidate SHA: " + candidate))
                self.assertEqual(graders["verdict"]["pattern"], r"^\W*VERDICT: %s\b" % (
                    "CHANGES REQUIRED" if refuse else "PASS"))
                self.assertEqual((graders["blind"]["target"], graders["blind"]["match"]),
                                 ("trace", "not_contains"))
                for name in ("answer-relayed", "verdict"):
                    self.assertEqual((graders[name]["target"], graders[name]["flags"]),
                                     ("last_message", "m"))
        relayed = re.compile(graders["answer-relayed"]["pattern"], re.M)
        for text in ("VERDICT: PASS", "**VERDICT: CHANGES REQUIRED**", "VERDICT: PASS WITH NOTES"):
            self.assertTrue(relayed.search("```\n%s\nReviewed SHA: x\n" % text), text)
        self.assertFalse(relayed.search("The VERDICT: PASS"))
        dispatched = re.compile(graders["reviewer-dispatched"]["input_match"])
        call = json.dumps({"description": "Review", "subagent_type": "manager-plugin:reviewer",
                           "prompt": "Read and follow x.\nBase SHA: %s   Candidate SHA: %s\n" % (
                               "0" * 40, candidate)})
        self.assertTrue(dispatched.search(call))
        self.assertFalse(dispatched.search(call.replace("manager-plugin:reviewer",
                                                        "general-purpose")))

    def test_the_answer_keys(self):
        for folder, key in self.keys.items():
            with self.subTest(case=folder):
                self.assertEqual(sorted(key), ["case", "kind", "level", "locations", "probe",
                                               "summary", "terms"])
                self.assertEqual(key["case"], folder.split("/")[-1])
                self.assertIn(key["kind"], score.KINDS)
                self.assertTrue(key["summary"] and key["probe"])
                compile(key["probe"], folder, "exec")
                located = key["kind"] in REFUSE
                self.assertEqual(bool(key["locations"]), located)
                self.assertEqual(bool(key["terms"]), located)
                for place in key["locations"]:
                    self.assertEqual(sorted(place), ["file", "lines", "text"])
                    low, high = place["lines"]
                    self.assertTrue(1 <= low <= high, place)
        self.assertEqual(sorted(score.answer_keys()), sorted(f.split("/")[-1]
                                                             for f in self.folders))


@unittest.skipUnless(portability.bash() and shutil.which("git"),
                     "needs bash (Git Bash on Windows, not System32's WSL bash) and git")
class ScaffoldTest(unittest.TestCase):
    """The workspaces the scaffolds build."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.addClassCleanup(portability.rmtree, cls.tmp)
        cls.folders = suite_cases()
        cls.work = {folder: build(folder, os.path.join(cls.tmp, str(number)))
                    for number, folder in enumerate(cls.folders)}

    def test_the_commits_the_prompt_names(self):
        for folder, work in self.work.items():
            base, candidate = DISPATCH.search(load(folder)["execution"]["prompt"]).groups()
            round2 = key_of(folder)["kind"].startswith("round2")
            with self.subTest(case=folder):
                self.assertEqual(git(work, "rev-parse", "HEAD"), candidate)
                self.assertEqual(git(work, "rev-parse", "origin/phase/P1"), candidate)
                self.assertEqual(git(work, "rev-parse", "origin/main"), base)
                self.assertEqual(git(work, "rev-parse", "main"), base)
                self.assertEqual(git(work, "symbolic-ref", "refs/remotes/origin/HEAD"),
                                 "refs/remotes/origin/main")
                self.assertEqual(git(work, "rev-list", "--reverse", "%s..%s" % (base, candidate))
                                 .split()[-1:], [candidate])
                self.assertEqual(len(git(work, "rev-list", "%s..%s" % (base, candidate)).split()),
                                 2 if round2 else 1)
                self.assertEqual(git(work, "rev-list", "--count", base), "1")
                self.assertEqual(git(work, "status", "--porcelain", "--ignored"), "")

    def test_a_scaffold_builds_the_same_commits_every_time(self):
        for number, folder in enumerate(self.folders):
            again = build(folder, os.path.join(self.tmp, "again%d" % number))
            with self.subTest(case=folder):
                self.assertEqual(git(again, "rev-parse", "HEAD"),
                                 git(self.work[folder], "rev-parse", "HEAD"))

    def test_a_scaffold_refuses_a_folder_that_holds_a_repository(self):
        folder = self.folders[0]
        work = self.work[folder]
        head = git(work, "rev-parse", "HEAD")
        self.assertEqual(scaffold_run(folder, work), (1, "fixture: this directory already holds "
                                                         "a repository or a fixture file\n"))
        self.assertEqual(git(work, "rev-parse", "HEAD"), head)

    def test_small_synthetic_repositories_without_the_key(self):
        for folder, work in self.work.items():
            files = git(work, "ls-files").split("\n")
            history = git(work, "log", "--all", "--name-only", "--format=").split()
            total = sum(len(read(os.path.join(work, path)).split("\n")) - 1 for path in files)
            with self.subTest(case=folder):
                self.assertLessEqual(total, MAX_LINES)
                self.assertFalse([p for p in files + history if p.endswith("answer.json")])
                self.assertIn("CLAUDE.md", files)
                self.assertIn("run_tests.py", files)

    def test_the_base_plan_passes_plan_check(self):
        for folder, work in self.work.items():
            plan = git(work, "show", "main:docs/LIVING_PLAN.md") + "\n"
            done = subprocess.run([sys.executable, PLAN_PY, "check"], input=plan.encode("utf-8"),
                                  capture_output=True,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            with self.subTest(case=folder):
                self.assertEqual((done.returncode, done.stdout.decode("utf-8")),
                                 (0, "ok: 1 phase\n"))
                self.assertIn("Status: done (PR #1)",
                              git(work, "show", "HEAD:docs/LIVING_PLAN.md"))

    def test_validation_passes_at_every_candidate_and_the_probe_tells_the_bug(self):
        for folder, work in self.work.items():
            key = key_of(folder)
            validation = python(work, "run_tests.py")
            log = validation.stderr.decode("utf-8", "replace")
            ran = re.search(r"(?m)^Ran ([0-9]+) tests?\b", log)
            probe = python(work, "-c", key["probe"])
            with self.subTest(case=folder):
                self.assertEqual(validation.returncode, 0, log)
                self.assertTrue(ran, log)
                self.assertEqual(int(ran.group(1)) == 0, folder.endswith("/rc-zero-tests"), log)
                self.assertEqual(probe.returncode != 0, key["kind"] in REFUSE,
                                 probe.stderr.decode("utf-8", "replace"))
                self.assertEqual(git(work, "status", "--porcelain", "--ignored"), "")

    def test_each_key_s_lines_hold_its_marker(self):
        for folder, work in self.work.items():
            for place in key_of(folder)["locations"]:
                lines = git(work, "show", "HEAD:" + place["file"]).split("\n")
                low, high = place["lines"]
                with self.subTest(case=folder, file=place["file"]):
                    self.assertLessEqual(high, len(lines))
                    self.assertTrue(any(place["text"] in line for line in lines[low - 1:high]))


ANSWER = """VERDICT: %s
Reviewed SHA: %s
Base SHA: %s
Blockers:
%s
Notes (non-blocking):
  N1. naming — pager.py:3 — readers may confuse it — rename
Acceptance: page_count(10, 5) is 2 → %s
Validation: python3 run_tests.py → pass (0) at the candidate
Not checked: none
Checkout untouched: HEAD = candidate, status empty
"""


def answer(verdict, *blockers):
    return ANSWER % (verdict, "1" * 40, "0" * 40, "\n".join("  " + b for b in blockers) or
                     "  none", "not met" if blockers else "met")


class ScoreTest(unittest.TestCase):
    """score.py on hand-written answers."""

    @classmethod
    def setUpClass(cls):
        cls.keys = score.answer_keys()

    def grade(self, case, text):
        return score.grade(self.keys[case], text)

    def test_parse(self):
        review = score.parse(answer("CHANGES REQUIRED",
                                    "B1. off by one — reproducible bug — pager.py:11 — wrong",
                                    "    for 10 items of 5 it gives 3",
                                    "B2. no test — missing required test — tests/test_pager.py:12"))
        self.assertEqual(review["verdict"], "CHANGES REQUIRED")
        self.assertEqual(review["blockers"], [
            "B1. off by one — reproducible bug — pager.py:11 — wrong for 10 items of 5 it gives 3",
            "B2. no test — missing required test — tests/test_pager.py:12"])
        self.assertEqual(score.parse(answer("PASS")), {"verdict": "PASS", "blockers": []})
        fenced = "```\n**VERDICT: PASS WITH NOTES**\nBlockers: none\nNotes (non-blocking):\n" \
                 "  N1. x — a.py:1 — y — z\n```\n"
        self.assertEqual(score.parse(fenced), {"verdict": "PASS WITH NOTES", "blockers": []})
        self.assertEqual(score.parse("I could not review it.")["verdict"], None)
        self.assertEqual(score.parse("Blockers:\n  - **B1.** bad — a.py:2\nNotes: none\n")
                         ["blockers"], ["- **B1.** bad — a.py:2"])

    def test_found_by_line_or_by_term(self):
        line = self.keys["rc-l1-off-by-one"]["locations"][0]["lines"][1]
        for blocker in ("B1. page count — reproducible bug — pager.py:%d — 10 items give 3" % line,
                        "B1. page count — bug — `pager.py:%d-%d`" % (line - 5, line + 1),
                        "B1. wrong count — unmet acceptance criterion — /tmp/x/pager.py — "
                        "page_count(10, 5) returns 3",
                        "B1. page_count is off by one for an exact multiple (pager.py)"):
            with self.subTest(blocker=blocker):
                result = self.grade("rc-l1-off-by-one", answer("CHANGES REQUIRED", blocker))
                self.assertEqual((result["outcome"], result["right"], result["extra"]),
                                 ("found", True, 0))

    def test_missed(self):
        for text in (answer("PASS"),
                     answer("CHANGES REQUIRED", "B1. no docs — rule breach — README.md:1 — x"),
                     answer("CHANGES REQUIRED", "B1. naming — rule breach — tests/test_pager.py:3 "
                                                "— off by one in the name"),
                     answer("CHANGES REQUIRED", "B1. wrong import — bug — pager.py:1 — unused")):
            with self.subTest(text=text.split("Blockers:")[1][:60]):
                result = self.grade("rc-l1-off-by-one", text)
                self.assertEqual((result["outcome"], result["right"]), ("missed", False))
        result = self.grade("rc-l1-off-by-one", "The reviewer did not answer.")
        self.assertEqual((result["outcome"], result["right"]), ("no verdict", False))

    def test_cross_file_and_doc_and_guard_cases(self):
        for case, blocker in (
                ("rc-l3-caller-not-updated", "B1. caller — bug — cli.py:8 — passes a string"),
                ("rc-l3-contract-change", "B1. KeyError — bug — service.py — record() breaks"),
                ("rc-l4-readme-drift", "B1. wrong default — record misstatement — README.md:7 — "
                                       "says 20, code uses 10"),
                ("rc-l4-plan-drift", "B1. change log — plan misstatement — "
                                     "docs/LIVING_PLAN.md:32 — no accent folding"),
                ("rc-weakened-test", "B1. skipped test — missing required test — "
                                     "tests/test_phone.py:20 — @unittest.skip hides a failure"),
                ("rc-zero-tests", "B1. zero tests — validation failure — run_tests.py — "
                                  "Ran 0 tests after the rename to tests/slug_test.py")):
            with self.subTest(case=case):
                self.assertEqual(self.grade(case, answer("CHANGES REQUIRED", blocker))["outcome"],
                                 "found")

    def test_false_alarms(self):
        for case in ("rc-decoy-for-else", "rc-clean-clamp"):
            with self.subTest(case=case):
                self.assertEqual(self.grade(case, answer("PASS"))["outcome"], "pass")
                self.assertEqual(self.grade(case, answer("PASS WITH NOTES"))["right"], True)
                alarm = self.grade(case, answer("CHANGES REQUIRED", "B1. x — bug — args.py:9"))
                self.assertEqual((alarm["outcome"], alarm["right"]), ("false alarm", False))
                odd = self.grade(case, answer("PASS", "B1. x — bug — args.py:9"))
                self.assertEqual(odd["outcome"], "false alarm")

    def test_round_2(self):
        fixed = self.grade("rc-round2-fixed", answer("PASS"))
        self.assertEqual((fixed["outcome"], fixed["right"]), ("accepted", True))
        refused = self.grade("rc-round2-fixed", answer("CHANGES REQUIRED", "B1. x — bug — a.py"))
        self.assertEqual((refused["outcome"], refused["right"]), ("rejected", False))
        caught = self.grade("rc-round2-unfixed", answer(
            "CHANGES REQUIRED", "B1. B1 still present — bug — ports.py:14 — 65536 accepted"))
        self.assertEqual((caught["outcome"], caught["right"], caught["named"]),
                         ("rejected", True, True))
        fooled = self.grade("rc-round2-unfixed", answer("PASS"))
        self.assertEqual((fooled["outcome"], fooled["right"]), ("accepted", False))

    def test_report_from_a_folder(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        files = {"rc-l1-off-by-one.txt": answer("CHANGES REQUIRED", "B1. off by one (pager.py)"),
                 "rc-l2-empty-input.txt": answer("PASS"),
                 "rc-decoy-for-else.1.txt": answer("PASS"),
                 "rc-decoy-for-else.2.txt": answer("CHANGES REQUIRED", "B1. x — bug — args.py"),
                 "rc-round2-unfixed.txt": answer("CHANGES REQUIRED", "B1. x — y — ports.py"),
                 "rc-clean-clamp.txt": "no answer", "notes.txt": "ignored"}
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        lines, totals = score.report(score.runs_from_folder(tmp, self.keys), self.keys)
        self.assertEqual(totals["runs"], 6)
        self.assertEqual(totals["recall"]["L1"], [1, 1])
        self.assertEqual(totals["recall"]["L2"], [0, 1])
        self.assertEqual(totals["recall"]["all"], [1, 2])
        self.assertEqual(totals["false alarms decoy"], [1, 2])
        self.assertEqual(totals["false alarms clean"], [0, 0])
        self.assertEqual(totals["round 2"], [1, 1])
        self.assertEqual(totals["no verdict"], 1)
        self.assertIn("recall: L1 1/1 (100%), L2 0/1 (0%), L3 0/0, L4 0/0, guard 0/0, "
                      "all 1/2 (50%)", lines)
        self.assertIn("false alarms: decoys 1/2 (50%), clean 0/0, together 1/2 (50%)", lines)
        done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), tmp],
                              capture_output=True, env=dict(os.environ,
                                                            PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(b"round 2 right: 1/1 (100%)", done.stdout)

    def test_report_from_a_run_result_and_its_trace(self):
        """The shape `claude plugin eval` writes: `cases[].arms.with[]` with `costUsd` and
        `tracePath`; the trace's events as the runner streams them."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        review = answer("CHANGES REQUIRED", "B1. off by one — bug — pager.py — exact multiple")

        def usage(n):
            return {"input_tokens": n, "cache_read_input_tokens": 10 * n,
                    "cache_creation_input_tokens": 2 * n, "output_tokens": n}
        events = [
            {"type": "system", "subtype": "init"},
            {"type": "assistant", "parent_tool_use_id": None, "message": {
                "id": "m1", "usage": usage(1), "content": [{
                    "type": "tool_use", "id": "toolu_r", "name": "Agent",
                    "input": {"subagent_type": "manager-plugin:reviewer", "prompt": "..."}}]}},
            {"type": "assistant", "parent_tool_use_id": "toolu_r", "message": {
                "id": "m2", "usage": usage(100), "content": [{"type": "text", "text": "x"}]}},
            {"type": "assistant", "parent_tool_use_id": "toolu_r", "message": {
                "id": "m2", "usage": usage(100), "content": [{"type": "text", "text": "y"}]}},
            {"type": "user", "parent_tool_use_id": None, "message": {"content": [{
                "type": "tool_result", "tool_use_id": "toolu_r",
                "content": [{"type": "text", "text": review}]}]}},
            {"type": "assistant", "parent_tool_use_id": None, "message": {
                "id": "m3", "usage": usage(2), "content": [{"type": "text", "text": "relayed"}]}},
            {"type": "result", "result": "Here it is, shortened."},
        ]
        with open(os.path.join(tmp, "trace.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(event) for event in events) + "\nnot json\n")
        result = {"schemaVersion": 1, "costUsd": 0.5, "cases": [
            {"name": "rc-l1-off-by-one", "arms": {"with": [
                {"score": 1, "costUsd": 0.41, "tracePath": "trace.jsonl", "graders": []}]}},
            {"name": "plugin-agent-spawn", "arms": {"with": [{"costUsd": 9}]}}]}
        path = os.path.join(tmp, "aggregate-result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
        runs = score.runs_from_result(path, self.keys)
        self.assertEqual([(r[0], r[1], r[3]) for r in runs], [("rc-l1-off-by-one", 1, 0.41)])
        self.assertEqual(runs[0][2], review)
        self.assertEqual(runs[0][4], {
            "all": {"input": 103, "cache read": 1030, "cache write": 206, "output": 103},
            "reviewer": {"input": 100, "cache read": 1000, "cache write": 200, "output": 100}})
        lines, totals = score.report(runs, self.keys)
        self.assertEqual((totals["recall"]["all"], totals["cost USD"]), ([1, 1], 0.41))
        self.assertIn("tokens reviewer: input 100, cache read 1000, cache write 200, output 100",
                      lines)
        done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), path, "--json"],
                              capture_output=True, env=dict(os.environ,
                                                            PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout.decode())["recall"]["L1"], [1, 1])
        for bad in ([], [path, "x"], [os.path.join(tmp, "missing.json")]):
            done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py")] + bad,
                                  capture_output=True)
            self.assertEqual(done.returncode, 2, bad)


class RunnerTest(unittest.TestCase):
    """run.py builds the command; nothing here starts a run."""

    def command(self, *argv):
        args = runner.parser().parse_args(list(argv))
        return runner.commands(args, "T")

    def test_defaults_and_options(self):
        run, score_command = self.command("--max-cost-usd", "15")
        self.assertEqual(run[:4], ["claude", "plugin", "eval", os.path.dirname(HERE)])
        text = " ".join(run)
        for part in ("--tag reviewer-calibration", "--ablation none", "--scaffold",
                     "--no-publish", "--allow-tools Agent Bash ToolSearch --model sonnet",
                     "--runs 1", "-j 1", "--max-cost-usd 15", "--output-dir "):
            self.assertIn(part, text)
        self.assertNotIn("--case", run)
        self.assertEqual(score_command[-1], os.path.join(
            HERE, "results", "reviewer-calibration-T", "aggregate-result.json"))
        run = self.command("--max-cost-usd", "2.5", "--model", "opus", "--runs", "3", "-j",
                           "2", "--case", "rc-l1-*")[0]
        self.assertIn("--model opus --runs 3 -j 2 --max-cost-usd 2.5", " ".join(run))
        self.assertEqual(run[-2:], ["--case", "rc-l1-*"])

    def test_a_ceiling_is_required_and_bad_values_refused(self):
        for argv in ([], ["--max-cost-usd", "0"], ["--max-cost-usd", "x"],
                     ["--max-cost-usd", "5", "--model", "haiku"],
                     ["--max-cost-usd", "5", "--runs", "0"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                    runner.parser().parse_args(argv)
        with self.assertRaises(SystemExit):
            self.command("--max-cost-usd", "5", "-j", "9")

    def test_dry_run_runs_nothing(self):
        done = subprocess.run([sys.executable, os.path.join(SUITE, "run.py"), "--dry-run",
                               "--max-cost-usd", "15"], capture_output=True,
                              env=dict(os.environ, PATH="", PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("claude plugin eval "))


class ReadmeTest(unittest.TestCase):
    """The README's command for the invariant cases leaves this suite out; it names this one."""

    def setUp(self):
        if not os.path.isfile(README):
            self.skipTest("no README.md beside this plugin copy")
        self.text = " ".join(read(README).split())

    def test_the_commands(self):
        command = re.search(r"claude plugin eval plugins/manager-plugin [^`]*", self.text).group(0)
        tags = [t for t in command.split("--tag ")[1].split(" --")[0].split() if t != "\\"]
        self.assertEqual(sorted(tags), sorted(INVARIANTS))
        self.assertIn("python3 plugins/manager-plugin/evals/reviewer-calibration/run.py "
                      "--max-cost-usd", self.text)
        self.assertIn("plugins/manager-plugin/evals/reviewer-calibration/", self.text)


if __name__ == "__main__":
    unittest.main()
