"""The reviewer-calibration suite (`reviewer-calibration/`), checked without a paid run:
python3 -m unittest discover -s <this folder>

- Every case is a valid `claude plugin eval` case (the format of `test_evals.py`), named `rc-01`
  to `rc-32` in a shuffled order per tier, with the same prompt and graders. The base tier,
  `rc-01` to `rc-20`, is tagged `reviewer-calibration` only; the hard tier, `rc-21` to `rc-32`,
  `reviewer-calibration-hard` only (`run.py --tier hard`). Nothing in a case tells its kind or
  tier; the answer keys (`evals-keys/reviewer-calibration/` at the repository root, outside the
  plugin folder) hold the mix each tier promises (base: 8 planted bugs over L1-L4, 2 guard cases,
  4 decoys, 4 clean diffs, 2 round-2 cases; hard: 7 planted over L1-L4, one of them with two
  findings, 1 round-2 case, 2 decoys, 1 clean diff, 1 nit).
- The blind grader's pattern is in none of what a run reads: the prompt, the manager's briefs,
  the reviewer agent, the workspace (files, commit messages, branches, git config) and the plan's
  phase section.
- Every scaffold builds the same two (round 2: three) commits every time, leaves the checkout on
  the candidate with a clean tree, refuses a folder that holds a repository and keeps its
  repository small (base: 150 lines, hard: 600); the base plan passes `plan.py check`; the
  commits the prompt names are the ones it builds; validation exits 0 at every candidate (the
  zero-tests case: with 0 tests run), so no planted bug is caught by the tests alone; each answer
  key's probe fails at a planted or unfixed candidate and passes at the others (a nit's too);
  each line range of a key (of each finding) holds its marker text.
- score.py grades hand-written answers right (found, missed, false alarm, round 2, no verdict,
  markdown answers, a wrong fault on the right file, a right one in other words, a key with two
  findings found, partial or missed, a nit passed or over-blocked), reads a run's result and
  trace, leaves invalid runs (an error, a failed run grader, a missing trace) out of the totals
  with a non-zero exit, writes the audit table and gives per-tier totals for a result of both
  tiers; run.py builds the command with its defaults, a required cost ceiling, the tier's tag,
  `--keep-temp` and the results folder, copies the traces and removes the kept sandboxes, refuses
  a path the blind grader would trip on, and exits non-zero when the eval or score.py does.
Without the key folder (the plugin copied alone) the tests that need the keys are skipped.
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
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(HERE, "reviewer-calibration")
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, SUITE)
sys.path.insert(0, PLUGIN)  # portability.py, in the plugin folder
import portability  # noqa: E402
import run as runner  # noqa: E402
import score  # noqa: E402
from test_evals import (CALIBRATION, CALIBRATION_TAGS, INVARIANTS, PLAN_PY, README,  # noqa: E402
                        case_folders, load, problems, read)

KINDS = {"planted": 10, "decoy": 4, "clean": 4, "round2-fixed": 1, "round2-unfixed": 1}
LEVELS = {"L1": 2, "L2": 2, "L3": 2, "L4": 2, "guard": 2}
HARD_KINDS = {"planted": 7, "round2-unfixed": 1, "decoy": 2, "clean": 1, "nit": 1}
HARD_LEVELS = {"L1": 1, "L2": 3, "L3": 1, "L4": 2}
MIX = {"base": (KINDS, LEVELS), "hard": (HARD_KINDS, HARD_LEVELS)}
IDS = {"base": ["rc-%02d" % n for n in range(1, 21)],
       "hard": ["rc-%02d" % n for n in range(21, 33)]}
TAGS = {"base": CALIBRATION, "hard": CALIBRATION + "-hard"}
GRADERS = ("answer-relayed", "blind", "reviewer-dispatched")
REFUSE = ("planted", "round2-unfixed")
DISPATCH = re.compile(r"Base SHA: ([0-9a-f]{40})   Candidate SHA: ([0-9a-f]{40})\n")
HINT = re.compile(r"(?<![A-Za-z0-9])(planted|decoy|clean|guard|round ?-?2|L[1-4]|calibration|"
                  r"drift|bug|trap|answer key|false alarm|off-by-one|weakened|zero-tests|nit|"
                  r"hard|tier|typo)"
                  r"(?![A-Za-z0-9])", re.I)
BLIND = ("reviewer-calibration", "evals-keys", "evals-results", "evals/results", "score.py",
         "test_reviewer_calibration", "answer.json")
MAX_LINES = {"base": 150, "hard": 600}
KEYS = score.answer_keys()
NAMES = {key["name"]: case for case, key in KEYS.items()}
needs_keys = unittest.skipUnless(KEYS, "no answer keys beside this plugin copy")
PASSED = [{"name": name, "passed": True, "weight": 1, "explanation": ""} for name in GRADERS]


def write_result(folder, runs, name=None):
    """An aggregate-result.json with one case and the given runs; returns its path."""
    path = os.path.join(folder, "aggregate-result.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "cases": [
            {"name": name or sorted(KEYS or {"rc-01": 1})[0], "arms": {"with": runs}}]}, fh)
    return path


def trace_with(text):
    """A trace whose reviewer answered `text`."""
    return "\n".join(json.dumps(event) for event in [
        {"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m1", "content": [
            {"type": "tool_use", "id": "t1", "name": "Agent",
             "input": {"subagent_type": "manager-plugin:reviewer"}}]}},
        {"type": "user", "parent_tool_use_id": None, "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": text}]}},
        {"type": "result", "result": text}]) + "\n"


def suite_cases():
    return [folder for folder in case_folders(skip=()) if folder.startswith(CALIBRATION + "/")]


def key_of(folder):
    return KEYS[folder.split("/")[-1]]


def tier_of(folder):
    """The tier of a case folder, from its id."""
    return [tier for tier, ids in IDS.items() if folder.split("/")[-1] in ids][0]


def places(key):
    """Every location of a key, over all its findings."""
    return [place for finding in score.findings_of(key) for place in finding["locations"]]


def case_of(name):
    """The id of the case whose key is labelled `name`."""
    return NAMES[name]


def blind_pattern():
    case = load(suite_cases()[0])
    return re.compile([g for g in case["graders"] if g["name"] == "blind"][0]["pattern"])


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


def python(work, *args, **kwargs):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable] + list(args), cwd=work, env=env,
                          capture_output=True, timeout=120, **kwargs)


class CaseTest(unittest.TestCase):
    """The case files, without a scaffold."""

    @classmethod
    def setUpClass(cls):
        cls.folders = suite_cases()
        cls.cases = {folder: load(folder) for folder in cls.folders}

    def test_neutral_ids(self):
        names = sorted(folder.split("/")[-1] for folder in self.folders)
        self.assertEqual(names, ["rc-%02d" % n for n in range(1, 33)])
        self.assertEqual(IDS["base"] + IDS["hard"], names)

    def test_one_tag_per_tier(self):
        self.assertEqual(TAGS, runner.TIER_TAGS)
        self.assertEqual(sorted(TAGS.values()), sorted(CALIBRATION_TAGS))
        for folder, case in self.cases.items():
            with self.subTest(case=folder):
                self.assertEqual(case["tags"], [TAGS[tier_of(folder)]])
                for text in (case["description"], case["execution"]["prompt"]):
                    self.assertNotIn("hard", text.lower())
                    self.assertNotIn("tier", text.lower())

    def test_every_case_is_a_valid_case_of_this_suite_only(self):
        for folder, case in self.cases.items():
            with self.subTest(case=folder):
                self.assertEqual(problems(case), [])
                self.assertEqual(case["name"], folder.split("/")[-1])
                self.assertIn(case["tags"], [[tag] for tag in CALIBRATION_TAGS])
                self.assertFalse(set(CALIBRATION_TAGS) & set(INVARIANTS))
                self.assertEqual((case["runs"], case["execution"]["model"]), (1, "sonnet"))
                self.assertEqual(case["context"], {"scaffold_script": "scaffold.sh"})
                self.assertEqual(sorted(case["execution"]["allowed_tools"]),
                                 sorted(["Agent", "Bash", "Read", "Glob", "Grep", "ToolSearch"]))
                self.assertFalse(os.path.isdir(os.path.join(HERE, *folder.split("/"), "mocks")))
        names = [case["name"] for case in self.cases.values()]
        self.assertEqual(sorted(set(f.split("/")[-1] for f in case_folders()) & set(names)), [],
                         "the invariant cases' tests must not take these in")

    def test_no_case_tells_its_kind(self):
        descriptions = set()
        for folder, case in self.cases.items():
            name = folder.split("/")[-1]
            descriptions.add(case["description"].replace(name, "<id>"))
            files = os.listdir(os.path.join(HERE, *folder.split("/")))
            scaffold = read(os.path.join(HERE, *folder.split("/"), "scaffold.sh"))
            commits = re.findall(r"(?m)^rc_commit [0-9]+ '([^']*)'", scaffold)
            with self.subTest(case=folder):
                self.assertTrue(commits)
                for text in [case["description"], case["execution"]["prompt"],
                             " ".join(files)] + commits:
                    self.assertIsNone(HINT.search(text), text)
                self.assertEqual(sorted(os.listdir(os.path.join(HERE, *folder.split("/"),
                                                                "graders"))),
                                 sorted(g + ".md" for g in GRADERS))
        self.assertEqual(descriptions, {"Review of pull request 1 in a practice repository (<id>)"})
        fixture = read(os.path.join(SUITE, "fixture.sh"))
        self.assertNotIn("answer.json", fixture)

    def test_the_prompt_is_the_dispatch_and_tells_nothing(self):
        prompts = {}
        for folder, case in self.cases.items():
            prompt = case["execution"]["prompt"]
            with self.subTest(case=folder):
                self.assertEqual(len(DISPATCH.findall(prompt)), 1)
                self.assertIn("`manager-plugin:reviewer`", prompt)
                self.assertIn("`git config eval.reviewerbrief`", prompt)
                for word in ("VERDICT", "answer.json", "expected", "calibration", "planted"):
                    self.assertNotIn(word.lower(), prompt.lower())
                prompts[folder] = DISPATCH.sub("", re.sub(r"(?m)^ *Previous blockers: .*\n", "",
                                                          prompt))
        self.assertEqual(len(set(prompts.values())), 1, "one prompt, apart from the commits")

    def test_the_graders(self):
        for folder, case in self.cases.items():
            graders = {grader["name"]: grader for grader in case["graders"]}
            candidate = DISPATCH.search(case["execution"]["prompt"]).group(2)
            with self.subTest(case=folder):
                self.assertEqual(sorted(graders), sorted(GRADERS))
                self.assertEqual(graders["reviewer-dispatched"]["tool"], "Agent")
                self.assertTrue(graders["reviewer-dispatched"]["input_match"].endswith(
                    "Candidate SHA: " + candidate))
                self.assertEqual((graders["blind"]["target"], graders["blind"]["match"]),
                                 ("trace", "not_contains"))
                self.assertEqual((graders["answer-relayed"]["target"],
                                  graders["answer-relayed"]["flags"]), ("last_message", "m"))
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
        blind = blind_pattern()
        for word in BLIND:
            self.assertTrue(blind.search("cat /x/%s/y" % word), word)
        self.assertFalse(blind.search("Read and follow /p/skills/manager/references/"
                                      "reviewer-brief.md"))

    def test_the_blind_pattern_is_in_nothing_a_run_reads(self):
        blind = blind_pattern()
        references = os.path.join(PLUGIN, "skills", "manager", "references")
        paths = [os.path.join(references, name) for name in sorted(os.listdir(references))
                 if name == "reviewer-brief.md" or name.startswith("brief-")]
        paths += [os.path.join(PLUGIN, "agents", "reviewer.md"),
                  os.path.join(PLUGIN, "skills", "manager", "SKILL.md")]
        self.assertIn(os.path.join(references, "reviewer-brief.md"), paths)
        for path in paths:
            with self.subTest(path=os.path.relpath(path, PLUGIN)):
                self.assertIsNone(blind.search(read(path)))
        for folder, case in self.cases.items():
            with self.subTest(case=folder):
                self.assertIsNone(blind.search(case["execution"]["prompt"]))
                self.assertIsNone(blind.search(case["description"]))
        self.assertIsNone(blind.search(read(os.path.join(SUITE, "fixture.sh"))))


@needs_keys
class KeyTest(unittest.TestCase):
    """The answer keys: outside the plugin, the promised mix, a shuffled order."""

    def test_the_keys_live_outside_the_plugin(self):
        self.assertFalse(os.path.abspath(score.KEYS).startswith(os.path.abspath(PLUGIN) + os.sep))
        self.assertEqual(os.path.basename(score.KEYS), CALIBRATION)
        self.assertEqual(os.path.basename(os.path.dirname(score.KEYS)), "evals-keys")
        for top, dirs, files in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d not in ("results", "__pycache__", ".git")]
            for name in files:
                with self.subTest(file=os.path.relpath(os.path.join(top, name), PLUGIN)):
                    self.assertNotEqual(name, "answer.json")
                    if name.endswith(".json"):
                        self.assertNotIn('"terms"', read(os.path.join(top, name)))
        self.assertEqual(sorted(KEYS), sorted(f.split("/")[-1] for f in suite_cases()))

    def test_the_mix(self):
        for tier, (mix, mix_levels) in MIX.items():
            keys = [KEYS[case] for case in IDS[tier]]
            with self.subTest(tier=tier):
                self.assertEqual(sorted(score.tier_of(key) for key in keys), [tier] * len(keys))
                kinds = [key["kind"] for key in keys]
                self.assertEqual({kind: kinds.count(kind) for kind in set(kinds)}, mix)
                levels = [key["level"] for key in keys if key["kind"] == "planted"]
                self.assertEqual({level: levels.count(level) for level in set(levels)},
                                 mix_levels)
                self.assertTrue(all(key["level"] is None for key in keys
                                    if key["kind"] != "planted"))
        self.assertTrue(all("tier" not in KEYS[case] for case in IDS["base"]))
        self.assertTrue(all(KEYS[case]["tier"] == "hard" for case in IDS["hard"]))
        self.assertEqual([len(score.findings_of(KEYS[case])) for case in IDS["hard"]
                          if "findings" in KEYS[case]], [2])
        self.assertLessEqual({"weakened-test", "zero-tests", "l1-off-by-one"}, set(NAMES))
        self.assertEqual(len(NAMES), len(KEYS))
        self.assertEqual(set(score.TIERS), set(MIX))

    def test_a_shuffled_order(self):
        """Base: no two neighbours of one kind. Hard: 7 planted cases of 12 cannot all be apart,
        so no two neighbours of one kind and level, and one planted pair at most."""
        for tier, ids in IDS.items():
            kinds = [KEYS[case]["kind"] for case in ids]
            levels = [KEYS[case]["level"] for case in ids]
            same = [n for n in range(1, len(kinds)) if kinds[n] == kinds[n - 1]]
            with self.subTest(tier=tier):
                if tier == "base":
                    self.assertFalse(same, kinds)
                else:
                    self.assertLessEqual(len(same), 1, kinds)
                    self.assertFalse([n for n in same if levels[n] == levels[n - 1]], levels)
                    self.assertTrue(all(kinds[n] == "planted" for n in same), kinds)
                planted = [level for level in levels if level]
                self.assertNotEqual(planted, sorted(planted))

    def test_the_answer_keys(self):
        for case, key in KEYS.items():
            with self.subTest(case=case):
                fields = ["case", "kind", "level", "name", "probe", "summary"]
                fields += ["tier"] if case in IDS["hard"] else []
                fields += ["findings"] if "findings" in key else ["alone", "locations", "terms"]
                self.assertEqual(sorted(key), sorted(fields))
                self.assertEqual(key["case"], case)
                self.assertIn(key["kind"], score.KINDS)
                self.assertIn(score.tier_of(key), score.TIERS)
                self.assertTrue(key["summary"] and key["probe"])
                compile(key["probe"], case, "exec")
                located = key["kind"] in REFUSE
                if "findings" in key:
                    self.assertEqual(key["kind"], "planted")
                    self.assertGreater(len(key["findings"]), 1)
                for finding in score.findings_of(key):
                    if "findings" in key:
                        self.assertEqual(sorted(finding), ["alone", "locations", "terms"])
                    self.assertEqual(bool(finding["alone"]), key["level"] == "guard")
                    self.assertEqual(bool(finding["locations"]), located)
                    self.assertEqual(bool(finding["terms"]), located)
                    for place in finding["locations"]:
                        self.assertEqual(sorted(place), ["file", "lines", "text"])
                        if place["lines"] is None:
                            self.assertIsNone(place["text"])
                            continue
                        low, high = place["lines"]
                        self.assertTrue(1 <= low <= high, place)
                    for term in finding["terms"] + finding["alone"]:
                        for part in term if isinstance(term, list) else [term]:
                            self.assertFalse(re.search(r"^[\w/]+\.(py|md)$", part), part)
                            self.assertNotIn(part.lower(), ("test", "tests", "bug", "wrong",
                                                            "missing", "default",
                                                            "docstring"))
        self.assertEqual(score.answer_keys(os.path.join(SUITE, "no-such-folder")), {})


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
            prompt = load(folder)["execution"]["prompt"]
            base, candidate = DISPATCH.search(prompt).groups()
            round2 = "Previous blockers:" in prompt
            with self.subTest(case=folder):
                self.assertEqual(git(work, "rev-parse", "HEAD"), candidate)
                self.assertEqual(git(work, "rev-parse", "origin/phase/P1"), candidate)
                self.assertEqual(git(work, "rev-parse", "origin/main"), base)
                self.assertEqual(git(work, "rev-parse", "main"), base)
                self.assertEqual(git(work, "symbolic-ref", "refs/remotes/origin/HEAD"),
                                 "refs/remotes/origin/main")
                self.assertEqual(len(git(work, "rev-list", "%s..%s" % (base, candidate)).split()),
                                 2 if round2 else 1)
                self.assertEqual(git(work, "rev-list", "--count", base), "1")
                self.assertEqual(git(work, "status", "--porcelain", "--ignored"), "")
                if KEYS:
                    self.assertEqual(round2, key_of(folder)["kind"].startswith("round2"))

    def test_the_brief_path_in_the_git_config(self):
        brief = os.path.join(PLUGIN, "skills", "manager", "references", "reviewer-brief.md")
        for folder, work in self.work.items():
            with self.subTest(case=folder):
                self.assertTrue(os.path.samefile(git(work, "config", "eval.reviewerbrief"),
                                                 brief))

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

    def test_small_synthetic_repositories_that_tell_nothing(self):
        blind = blind_pattern()
        for folder, work in self.work.items():
            files = git(work, "ls-files").split("\n")
            history = git(work, "log", "--all", "--name-only", "--format=").split()
            messages = git(work, "log", "--all", "--format=%B")
            branches = git(work, "for-each-ref", "--format=%(refname)")
            config = git(work, "config", "--local", "--list")
            plan = git(work, "show", "HEAD:docs/LIVING_PLAN.md") + "\n"
            phase = python(work, PLAN_PY, "phase", "P1", input=plan.encode("utf-8"))
            total = sum(len(read(os.path.join(work, path)).split("\n")) - 1 for path in files)
            with self.subTest(case=folder):
                self.assertEqual(phase.returncode, 0, phase.stderr)
                self.assertLessEqual(total, MAX_LINES[tier_of(folder)])
                self.assertIn("CLAUDE.md", files)
                self.assertIn("run_tests.py", files)
                for text in [messages, branches, " ".join(files + history)]:
                    self.assertIsNone(HINT.search(text), text)
                for text in [messages, branches, config, " ".join(files + history),
                             phase.stdout.decode("utf-8")] + [
                                 read(os.path.join(work, path)) for path in files]:
                    self.assertIsNone(blind.search(text), text[:200])
                self.assertNotIn(os.path.basename(SUITE), work)

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

    @needs_keys
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
                self.assertEqual(int(ran.group(1)) == 0, key["name"] == "zero-tests", log)
                self.assertEqual(probe.returncode != 0, key["kind"] in REFUSE,
                                 probe.stderr.decode("utf-8", "replace"))
                self.assertEqual(git(work, "status", "--porcelain", "--ignored"), "")

    @needs_keys
    def test_each_key_s_lines_hold_its_marker(self):
        for folder, work in self.work.items():
            base = DISPATCH.search(load(folder)["execution"]["prompt"]).group(1)
            for place in places(key_of(folder)):
                with self.subTest(case=folder, file=place["file"]):
                    if place["lines"] is None:  # a file the candidate removed
                        self.assertTrue(git(work, "show", "%s:%s" % (base, place["file"])))
                        continue
                    lines = git(work, "show", "HEAD:" + place["file"]).split("\n")
                    low, high = place["lines"]
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



@needs_keys
class ScoreTest(unittest.TestCase):
    """score.py on hand-written answers."""

    def grade(self, name, text):
        return score.grade(KEYS[case_of(name)], text)

    def outcome(self, name, *blockers):
        return self.grade(name, answer("CHANGES REQUIRED", *blockers))["outcome"]

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

    def test_parse_markdown_with_no_blocker(self):
        for blockers in ("**Blockers:** none", "**Blockers:**\nnone", "Blockers:\n  none.",
                         "Blockers: —", "Blockers: -", "**Blockers:** _none_",
                         "## Blockers\n\n`none`\n", "Blockers:\n  —", "**Blockers**: None found"):
            text = "**VERDICT: PASS**\n\n%s\n\n**Notes (non-blocking):**\n- N1. x — a.py:1\n" \
                   "**Acceptance:** met\n" % blockers
            with self.subTest(blockers=blockers):
                self.assertEqual(score.parse(text), {"verdict": "PASS", "blockers": []})

    def test_parse_markdown_entries(self):
        for entries in ("1. bad — a.py:2\n2. worse — b.py:3", "- bad — a.py:2\n- worse — b.py:3",
                        "* bad — a.py:2\n* worse — b.py:3", "1) bad — a.py:2\n2) worse — b.py:3",
                        "- **B1.** bad — a.py:2\n- **B2.** worse — b.py:3",
                        "**B1.** bad — a.py:2\n**B2.** worse — b.py:3"):
            text = "VERDICT: CHANGES REQUIRED\n**Blockers:**\n%s\n**Notes:** none\n" % entries
            with self.subTest(entries=entries):
                found = score.parse(text)["blockers"]
                self.assertEqual(len(found), 2, found)
                self.assertIn("a.py:2", found[0])
                self.assertIn("b.py:3", found[1])

    def test_a_bolded_markdown_review_scores_found(self):
        line = KEYS[case_of("l1-off-by-one")]["locations"][0]["lines"][0]
        text = ("**VERDICT: CHANGES REQUIRED**\n\n**Reviewed SHA:** `%s`\n\n**Blockers:**\n\n"
                "1. **Page count** — reproducible bug — `pager.py:%d` — 10 items of 5 give 3 "
                "pages\n\n**Notes (non-blocking):** none\n\n**Acceptance:** not met\n"
                % ("1" * 40, line))
        result = self.grade("l1-off-by-one", text)
        self.assertEqual((result["outcome"], result["right"], result["extra"]), ("found", True, 0))

    def test_found_by_line_or_by_term(self):
        line = KEYS[case_of("l1-off-by-one")]["locations"][0]["lines"][1]
        for blocker in ("B1. page count — reproducible bug — pager.py:%d — 10 items give 3" % line,
                        "B1. page count — bug — `pager.py:%d-%d`" % (line - 5, line + 1),
                        "B1. wrong count — unmet acceptance criterion — /tmp/x/pager.py — "
                        "page_count(10, 5) returns 3",
                        "B1. page_count is off by one for an exact multiple (pager.py)"):
            with self.subTest(blocker=blocker):
                result = self.grade("l1-off-by-one", answer("CHANGES REQUIRED", blocker))
                self.assertEqual((result["outcome"], result["right"], result["extra"]),
                                 ("found", True, 0))

    def test_missed(self):
        for text in (answer("PASS"),
                     answer("CHANGES REQUIRED", "B1. no docs — rule breach — README.md:1 — x"),
                     answer("CHANGES REQUIRED", "B1. naming — rule breach — tests/test_pager.py:3 "
                                                "— off by one in the name"),
                     answer("CHANGES REQUIRED", "B1. wrong import — bug — pager.py:1 — unused")):
            with self.subTest(text=text.split("Blockers:")[1][:60]):
                result = self.grade("l1-off-by-one", text)
                self.assertEqual((result["outcome"], result["right"]), ("missed", False))
        result = self.grade("l1-off-by-one", "The reviewer did not answer.")
        self.assertEqual((result["outcome"], result["right"]), ("no verdict", False))

    def test_a_wrong_fault_on_the_right_file_is_missed(self):
        for name, blocker in (
                ("l3-caller-not-updated", "B1. No test for the CLI — cli.py:1"),
                ("l3-contract-change", "B1. Missing type hints — store.py:12 — find should "
                                       "record its return type"),
                ("l2-wrong-condition", "B1. docstring does not mention max_attempts — "
                                       "retry.py:12"),
                ("l4-readme-drift", "B1. README.md:3 — the default heading wording is vague")):
            with self.subTest(case=name):
                self.assertEqual(self.outcome(name, blocker), "missed")

    def test_cross_file_and_doc_and_guard_cases(self):
        for name, blocker in (
                ("l3-caller-not-updated", "B1. caller — bug — cli.py:8 — passes a string"),
                ("l3-caller-not-updated", "B1. load() now takes a list but cli.py hands it "
                                          "argv[1], so it iterates the characters"),
                ("l3-contract-change", "B1. KeyError — bug — service.py — record() breaks"),
                ("l3-contract-change", "B1. service.py still does an is None check, and the "
                                       "first visit of a page now raises"),
                ("l2-wrong-condition", "B1. retry.py — a 429 never counts against the attempt "
                                       "limit, so it retries forever"),
                ("l4-readme-drift", "B1. wrong default — record misstatement — README.md:7 — "
                                    "says 20, code uses 10"),
                ("l4-readme-drift", "B1. README.md says the page size defaults to 20; the "
                                    "code's default is 10"),
                ("l4-plan-drift", "B1. change log — plan misstatement — "
                                  "docs/LIVING_PLAN.md:32 — no accent folding"),
                ("weakened-test", "B1. skipped test — missing required test — "
                                  "tests/test_phone.py:20 — @unittest.skip hides a failure"),
                ("zero-tests", "B1. zero tests — validation failure — run_tests.py — "
                               "Ran 0 tests after the rename to tests/slug_test.py"),
                ("zero-tests", "B1. tests/test_slug.py was renamed and is not discovered"),
                ("zero-tests", "B1. validation failure — the suite ran 0 tests"),
                ("weakened-test", "B1. the international-number test is skipped")):
            with self.subTest(case=name, blocker=blocker):
                self.assertEqual(self.outcome(name, blocker), "found")
        self.assertEqual(self.outcome("zero-tests", "B1. tests/test_slug.py:4 — weak assert"),
                         "missed")

    def test_false_alarms(self):
        for name in ("decoy-for-else", "clean-clamp"):
            with self.subTest(case=name):
                self.assertEqual(self.grade(name, answer("PASS"))["outcome"], "pass")
                self.assertEqual(self.grade(name, answer("PASS WITH NOTES"))["right"], True)
                alarm = self.grade(name, answer("CHANGES REQUIRED", "B1. x — bug — args.py:9"))
                self.assertEqual((alarm["outcome"], alarm["right"]), ("false alarm", False))
                odd = self.grade(name, answer("PASS", "B1. x — bug — args.py:9"))
                self.assertEqual(odd["outcome"], "false alarm")

    def test_round_2(self):
        for verdict in ("PASS", "PASS WITH NOTES"):
            fixed = self.grade("round2-fixed", answer(verdict))
            self.assertEqual((fixed["outcome"], fixed["right"]), ("accepted", True))
        refused = self.grade("round2-fixed", answer("CHANGES REQUIRED", "B1. x — bug — a.py"))
        self.assertEqual((refused["outcome"], refused["right"]), ("rejected", False))
        caught = self.grade("round2-unfixed", answer(
            "CHANGES REQUIRED", "B1. B1 still present — bug — ports.py:14 — 65536 accepted"))
        self.assertEqual((caught["outcome"], caught["right"], caught["named"]),
                         ("rejected", True, True))
        fooled = self.grade("round2-unfixed", answer("PASS"))
        self.assertEqual((fooled["outcome"], fooled["right"]), ("accepted", False))

    def test_parse_headings_without_a_colon(self):
        for heading in ("**Blockers**", "## Blockers", "### Blockers", "#### **Blockers**"):
            text = ("VERDICT: CHANGES REQUIRED\n%s\n\n1. bad — a.py:2\n\n## Notes "
                    "(non-blocking)\n- N1. fine — b.py:1\n" % heading)
            with self.subTest(heading=heading):
                self.assertEqual(score.parse(text)["blockers"], ["1. bad — a.py:2"])
        for none in ("No blockers.", "n/a", "N/A", "none.", "- No blockers", "**N/A**"):
            text = "**VERDICT: PASS**\n## Blockers\n%s\n## Notes\nnone\n" % none
            with self.subTest(none=none):
                self.assertEqual(score.parse(text), {"verdict": "PASS", "blockers": []})
            self.assertEqual(score.parse("VERDICT: PASS\nBlockers: %s\n" % none)["blockers"], [])

    def test_loose_wrong_blockers_are_missed(self):
        for name, blocker in (
                ("l3-contract-change", "B1. store.py:13 — KeyError carries no message"),
                ("l3-caller-not-updated", "B1. cli.py:2 — usage help not updated; it is a "
                                          "string constant"),
                ("l4-plan-drift", "B1. docs/LIVING_PLAN.md:3 — the plan folder is not named"),
                ("l4-readme-drift", "B1. README.md:20 — a typo in the install heading"),
                ("l1-wrong-operator", "B1. discount.py:3 — the boundary values are not "
                                      "documented"),
                ("weakened-test", "B1. phone.py:3 — an unreachable branch in format()"),
                ("zero-tests", "B1. no tests cover the new length option"),
                ("l2-empty-input", "B1. stats.py:3 — empty docstring on the module")):
            with self.subTest(case=name):
                self.assertEqual(self.outcome(name, blocker), "missed")

    def test_right_blockers_in_other_words_are_found(self):
        for name, blocker in (
                ("l3-contract-change", "B1. service.py record() relies on find returning None "
                                       "for a new page; it now raises"),
                ("l1-wrong-operator", "B1. discount.py uses a strict comparison, so a total of "
                                      "exactly 100 gets no discount"),
                ("zero-tests", "B1. the tests were renamed to tests/slug_test.py, which "
                               "run_tests.py does not discover"),
                ("l4-plan-drift", "B1. docs/LIVING_PLAN.md claims folding, the code keeps "
                                  "accents"),
                ("weakened-test", "B1. the failing test is skipped instead of fixed")):
            with self.subTest(case=name):
                self.assertEqual(self.outcome(name, blocker), "found")

    def test_invalid_runs_are_left_out_and_fail_the_score(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        name = case_of("l1-off-by-one")
        with open(os.path.join(tmp, "t.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(trace_with(answer("CHANGES REQUIRED", "B1. off by one (pager.py)")))
        good = {"tracePath": "t.jsonl", "error": None, "graders": PASSED, "costUsd": 0.1}
        cases = {"an error": dict(good, error="session crashed"),
                 "grader blind failed": dict(good, graders=[dict(g, passed=g["name"] != "blind")
                                                            for g in PASSED]),
                 "grader reviewer-dispatched failed": dict(good, graders=[
                     dict(g, passed=g["name"] != "reviewer-dispatched") for g in PASSED]),
                 "grader answer-relayed failed": dict(good, graders=[
                     dict(g, passed=g["name"] != "answer-relayed") for g in PASSED]),
                 "trace missing": dict(good, tracePath=os.path.join(tmp, "gone.jsonl"))}
        for reason, run in cases.items():
            with self.subTest(reason=reason):
                path = write_result(tmp, [good, run], name)
                runs = score.runs_from_result(path, KEYS)
                self.assertEqual(runs[0][5], [])
                self.assertTrue(any(r.startswith(reason.replace("an error", "error"))
                                    for r in runs[1][5]), runs[1][5])
                lines, totals = score.report(runs, KEYS)
                self.assertEqual((totals["runs"], totals["invalid"], totals["recall"]["all"]),
                                 (1, 1, [1, 1]))
                self.assertTrue([line for line in lines if line.startswith("INVALID %s run 2"
                                                                           % name)])
                done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), path],
                                      capture_output=True,
                                      env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn(b"invalid run", done.stderr)
        path = write_result(tmp, [good], name)
        done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), path],
                              capture_output=True, env=dict(os.environ,
                                                            PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_audit(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        name = case_of("l1-off-by-one")
        line = KEYS[name]["locations"][0]["lines"][0]
        with open(os.path.join(tmp, "t.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(trace_with(answer("CHANGES REQUIRED", "B1. page count — pager.py:%d — " %
                                       line + "x" * 300, "B2. naming | style — README.md:1")))
        path = write_result(tmp, [{"tracePath": "t.jsonl", "error": None, "graders": PASSED},
                                  {"tracePath": "lost.jsonl", "error": None,
                                   "graders": PASSED}], name)
        done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), path],
                              capture_output=True, env=dict(os.environ,
                                                            PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 1)
        rows = read(os.path.join(tmp, "audit.md")).split("\n")
        self.assertIn("| case | run | kind | verdict | blocker | match | invalid |", rows)
        first = [row for row in rows if row.startswith("| %s | 1 |" % name)]
        self.assertEqual(len(first), 2)
        self.assertIn("pager.py:%d-%d cited" % (line, line), first[0])
        self.assertIn("...", first[0])
        self.assertLess(len(first[0].split(" | ")[4]), 201)
        self.assertIn("naming \\| style", first[1])
        self.assertIn("| no match | - |", first[1])
        second = [row for row in rows if row.startswith("| %s | 2 |" % name)]
        self.assertEqual(len(second), 1)
        self.assertIn("trace missing", second[0])

    def test_report_from_a_folder(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        files = {"l1-off-by-one.txt": answer("CHANGES REQUIRED", "B1. off by one (pager.py)"),
                 "l2-empty-input.txt": answer("PASS"),
                 "decoy-for-else.1.txt": answer("PASS"),
                 "decoy-for-else.2.txt": answer("CHANGES REQUIRED", "B1. x — bug — args.py"),
                 "round2-unfixed.txt": answer("CHANGES REQUIRED", "B1. x — y — ports.py"),
                 "clean-clamp.txt": "no answer"}
        for name, text in files.items():
            label, rest = name.split(".", 1)
            with open(os.path.join(tmp, case_of(label) + "." + rest), "w",
                      encoding="utf-8") as fh:
                fh.write(text)
        with open(os.path.join(tmp, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("ignored")
        lines, totals = score.report(score.runs_from_folder(tmp, KEYS), KEYS)
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
            {"name": case_of("l1-off-by-one"), "arms": {"with": [
                {"score": 1, "costUsd": 0.41, "tracePath": "trace.jsonl", "error": None,
                 "graders": PASSED}]}},
            {"name": "plugin-agent-spawn", "arms": {"with": [{"costUsd": 9}]}}]}
        path = os.path.join(tmp, "aggregate-result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
        runs = score.runs_from_result(path, KEYS)
        self.assertEqual([(r[0], r[1], r[3], r[5]) for r in runs],
                         [(case_of("l1-off-by-one"), 1, 0.41, [])])
        self.assertEqual(runs[0][2], review)
        self.assertEqual(runs[0][4], {
            "all": {"input": 103, "cache read": 1030, "cache write": 206, "output": 103},
            "reviewer": {"input": 100, "cache read": 1000, "cache write": 200, "output": 100}})
        lines, totals = score.report(runs, KEYS)
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

    def test_tokens_come_from_the_result_event_when_it_has_model_usage(self):
        """The assistant snapshots under-count output and miss the reviewer's last message, so
        the session's `modelUsage` wins; the reviewer is that minus the main thread's `usage`."""
        events = [
            {"type": "assistant", "parent_tool_use_id": None, "message": {
                "id": "m1", "usage": {"input_tokens": 1, "output_tokens": 1}, "content": [{
                    "type": "tool_use", "id": "toolu_r", "name": "Agent",
                    "input": {"subagent_type": "manager-plugin:reviewer"}}]}},
            {"type": "result", "result": "VERDICT: PASS", "usage": {
                "input_tokens": 6, "cache_read_input_tokens": 400,
                "cache_creation_input_tokens": 100, "output_tokens": 1300},
             "modelUsage": {"a": {"inputTokens": 10, "cacheReadInputTokens": 1000,
                                  "cacheCreationInputTokens": 300, "outputTokens": 2800},
                            "b": {"inputTokens": 6, "outputTokens": 95}}}]
        self.assertEqual(score.from_trace(events)[1], {
            "all": {"input": 16, "cache read": 1000, "cache write": 300, "output": 2895},
            "reviewer": {"input": 10, "cache read": 600, "cache write": 200, "output": 1595}})
        events[0]["message"]["content"][0]["input"]["subagent_type"] = "other"
        self.assertEqual(score.from_trace(events)[1]["reviewer"], {})


@needs_keys
class HardScoreTest(unittest.TestCase):
    """score.py on the hard tier: its terms, a key with two findings, a nit, totals per tier."""

    def grade(self, name, *blockers, **kwargs):
        verdict = kwargs.get("verdict", "CHANGES REQUIRED")
        return score.grade(KEYS[case_of(name)], answer(verdict, *blockers))

    def outcome(self, name, *blockers):
        return self.grade(name, *blockers)["outcome"]

    def folder(self, files):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for name, text in files.items():
            label, rest = name.split(".", 1)
            with open(os.path.join(tmp, case_of(label) + "." + rest), "w",
                      encoding="utf-8") as fh:
                fh.write(text)
        return tmp

    def test_right_blockers_are_found(self):
        for name, blocker in (
                ("l2-mutable-default", "B1. tags.py:9 — `seen=[]` is a mutable default: the "
                                       "hashtags of earlier calls accumulate"),
                ("l2-mutable-default", "B1. hashtags (tags.py) also returns the tags of every "
                                       "earlier call; the list is shared between calls"),
                ("l3-tuple-to-dict", "B1. release.py:13 still indexes the result with "
                                     "parsed[0]: bump raises KeyError"),
                ("l3-tuple-to-dict", "B1. versions.py now returns a dict, but release.bump reads "
                                     "it by position, so `cli.py bump` raises KeyError"),
                ("l1-condition-dropped-in-move", "B1. pricing.py:28 — the HOME_COUNTRY check "
                                                 "was dropped: orders abroad from 50 ship free"),
                ("l1-condition-dropped-in-move", "B1. pricing.shipping (pricing.py) gives free "
                                                 "shipping to foreign orders over 50"),
                ("l4-binding-decision", "B1. config.py:15 — int() raises ValueError for a bad "
                                        "port, against B2 (load never raises)"),
                ("l4-binding-decision", "B1. docs/LIVING_PLAN.md — binding decision B2 broken: "
                                        "load raises for a non-numeric port"),
                ("l4-half-up", "B1. ratings.py:15 — round() rounds half to even, so 2.5 gives 2; "
                               "the plan says half up"),
                ("l4-half-up", "B1. tests/test_ratings.py:21 asserts banker's rounding, against "
                               "the acceptance"),
                ("l2-late-binding", "B1. limits.py:19 — late binding: every lambda sees the last "
                                    "maximum"),
                ("l2-late-binding", "B1. the closures in limit_checks (limits.py) all capture "
                                    "the loop variable")):
            with self.subTest(case=name, blocker=blocker):
                self.assertEqual(self.outcome(name, blocker), "found")
        unfixed = self.grade("round2-unfixed-leap-year", "B1. B1 still present — months.py:19 — "
                                                         "year % 4 makes 1900 a leap year")
        self.assertEqual((unfixed["outcome"], unfixed["named"]), ("rejected", True))

    def test_wrong_faults_on_the_right_file_are_missed(self):
        for name, blocker in (
                ("l2-mutable-default", "B1. tags.py:5 — normalize keeps inner punctuation"),
                ("l3-tuple-to-dict", "B1. versions.py:4 — parse_version has no type hints"),
                ("l3-tuple-to-dict", "B1. release.py:1 — the module docstring is vague"),
                ("l1-condition-dropped-in-move", "B1. pricing.py:3 — VAT_RATE belongs in the "
                                                 "settings"),
                ("l4-binding-decision", "B1. config.py:4 — DEFAULT_PORT is not in the README"),
                ("l4-half-up", "B1. ratings.py:5 — average gives a float for whole ratings"),
                ("l2-late-binding", "B1. limits.py:9 — parse_limits fails on a line with two "
                                    "equal signs")):
            with self.subTest(case=name):
                self.assertEqual(self.outcome(name, blocker), "missed")

    def test_two_findings(self):
        median = ("B1. stats.py:18 — the median of an even count is the upper middle value: "
                  "[1, 2, 3, 4] gives 3")
        order = "B2. summary sorts the caller's list in place (stats.py:17)"
        other = "B3. no test with an even count — tests/test_stats.py"
        both = self.grade("l2-two-faults", median, order)
        self.assertEqual((both["outcome"], both["right"], both["findings"], both["extra"]),
                         ("found", True, [2, 2], 0))
        self.assertTrue(both["matches"][0][1].startswith("finding 1: stats.py"))
        self.assertTrue(both["matches"][1][1].startswith("finding 2: stats.py"))
        for blocker in (median, order):
            one = self.grade("l2-two-faults", blocker, other)
            self.assertEqual((one["outcome"], one["right"], one["findings"], one["extra"]),
                             ("partial", False, [1, 2], 1))
        none = self.grade("l2-two-faults", "B1. stats.py:3 — the module docstring is vague")
        self.assertEqual((none["outcome"], none["right"], none["findings"]),
                         ("missed", False, [0, 2]))
        self.assertEqual(self.grade("l2-two-faults", verdict="PASS")["outcome"], "missed")
        silent = score.grade(KEYS[case_of("l2-two-faults")], "no answer")
        self.assertEqual((silent["outcome"], silent["findings"]), ("no verdict", [0, 2]))
        one = self.grade("l2-two-faults", "B1. stats.py — summary sorts values in place, and "
                                          "for an even count the median is not the mean of the "
                                          "two middle values")
        self.assertEqual((one["outcome"], one["findings"]), ("found", [2, 2]))
        self.assertIn("finding 1: ", one["matches"][0][1])
        self.assertIn("; finding 2: ", one["matches"][0][1])
        # A cited range spanning both findings, or a loose word, credits only the finding named.
        for blocker in ("B1. stats.py:9-18 — summary sorts the caller's list in place",
                        "B1. summary mutates the input list; stats.py sorts it in place even "
                        "when the median is all that is needed",
                        "B1. stats.py:18 — for an even count the median is the upper middle "
                        "value; use sorted(values) and average the two middle values"):
            with self.subTest(blocker=blocker):
                half = self.grade("l2-two-faults", blocker)
                self.assertEqual((half["outcome"], half["right"], half["findings"]),
                                 ("partial", False, [1, 2]))
        # Natural wordings of one bug credit that finding alone; a citation credits a finding
        # that it overlaps when it is clear of the other's (stats.py:9-18 names neither).
        for number, blocker in (
                (1, "B1. stats.py:18 — the median is wrong when len(values) is even"),
                (1, "B1. stats.py — for even-numbered lists the median ignores the middle pair"),
                (1, "B1. stats.py — the median should average the two central elements"),
                (1, "B1. stats.py — median of [1, 2, 3, 4] gives 3 instead of 2.5; the code "
                    "sorts values then indexes len // 2"),
                (1, "B1. stats.py:18 — wrong value returned"),
                (2, "B1. stats.py:17 — the input list is modified"),
                (2, "B1. stats.py — the caller's values are reordered"),
                (2, "B1. stats.py:16 — ordered is the same object as values, so .sort() "
                    "changes it"),
                (2, "B1. stats.py — `ordered = values` should be `ordered = sorted(values)`"),
                (2, "B1. stats.py — summary alters the argument list"),
                (2, "B1. stats.py — the passed-in list gets sorted"),
                (2, "B1. stats.py:16-17 — wrong"),
                (2, "B1. stats.py:15-17 — wrong")):
            with self.subTest(blocker=blocker):
                half = self.grade("l2-two-faults", blocker)
                self.assertEqual((half["outcome"], half["findings"]), ("partial", [1, 2]))
                self.assertTrue(half["matches"][0][1].startswith("finding %d: " % number),
                                half["matches"][0][1])
        for blocker in ("B1. stats.py:9-18 — wrong", "B1. stats.py:16-18 — wrong"):
            self.assertEqual(self.grade("l2-two-faults", blocker)["outcome"], "missed")
        self.assertEqual(self.grade("l1-off-by-one", "B1. off by one (pager.py)")["findings"],
                         [1, 1])

    def test_nit(self):
        for verdict in ("PASS", "PASS WITH NOTES"):
            with self.subTest(verdict=verdict):
                passed = self.grade("nit-docstring-typo", verdict=verdict)
                self.assertEqual((passed["outcome"], passed["right"]), ("pass", True))
        for result in (self.grade("nit-docstring-typo", "B1. typo — names.py:11 — seperated"),
                       self.grade("nit-docstring-typo", verdict="CHANGES REQUIRED"),
                       self.grade("nit-docstring-typo", "B1. typo — names.py:11",
                                  verdict="PASS WITH NOTES")):
            self.assertEqual((result["outcome"], result["right"]), ("over-blocking", False))
        silent = score.grade(KEYS[case_of("nit-docstring-typo")], "no answer")
        self.assertEqual((silent["outcome"], silent["right"]), ("no verdict", False))

    def test_totals_per_tier(self):
        tmp = self.folder({
            "l1-off-by-one.txt": answer("CHANGES REQUIRED", "B1. off by one (pager.py)"),
            "decoy-for-else.txt": answer("PASS"),
            "nit-docstring-typo.1.txt": answer("PASS WITH NOTES"),
            "nit-docstring-typo.2.txt": answer("CHANGES REQUIRED", "B1. typo — names.py:11"),
            "decoy-memo-default.txt": answer("CHANGES REQUIRED", "B1. mutable default — "
                                                                 "sequences.py:11"),
            "l2-two-faults.txt": answer("CHANGES REQUIRED", "B1. stats.py sorts in place")})
        lines, totals = score.report(score.runs_from_folder(tmp, KEYS), KEYS)
        self.assertEqual(totals["runs"], 6)
        self.assertEqual(totals["over-blocking nit"], [1, 2])
        self.assertEqual(totals["false alarms decoy"], [1, 2])
        self.assertEqual(totals["false alarms"], [1, 2])
        self.assertEqual(totals["recall"]["L1"], [1, 1])
        self.assertEqual(totals["recall"]["L2"], [1, 2])
        self.assertEqual(totals["recall"]["all"], [2, 3])
        self.assertEqual(sorted(totals["tiers"]), ["base", "hard"])
        hard, base = totals["tiers"]["hard"], totals["tiers"]["base"]
        self.assertEqual((hard["runs"], hard["over-blocking nit"], hard["recall"]["all"],
                          hard["false alarms decoy"], hard["invalid"]),
                         (4, [1, 2], [1, 2], [1, 1], 0))
        self.assertEqual((base["runs"], base["over-blocking nit"], base["recall"]["all"],
                          base["false alarms decoy"]), (2, [0, 0], [1, 1], [0, 1]))
        self.assertIn("over-blocking nit: 1/2 (50%)", lines)
        self.assertIn("tier hard: over-blocking nit: 1/2 (50%)", lines)
        self.assertIn("tier hard: recall: L1 0/0, L2 1/2 (50%), L3 0/0, L4 0/0, guard 0/0, "
                      "all 1/2 (50%)", lines)
        self.assertIn("tier base: recall: L1 1/1 (100%), L2 0/0, L3 0/0, L4 0/0, guard 0/0, "
                      "all 1/1 (100%)", lines)
        self.assertIn("tier hard: false alarms: decoys 1/1 (100%), clean 0/0, together "
                      "1/1 (100%)", lines)
        self.assertFalse([line for line in lines if line.startswith("tier base: over-")])
        self.assertTrue([line for line in lines if line.startswith(case_of("l2-two-faults"))
                         and "| partial (1/2 findings) |" in line])
        done = subprocess.run([sys.executable, os.path.join(SUITE, "score.py"), tmp, "--json"],
                              capture_output=True, env=dict(os.environ,
                                                            PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout.decode())["tiers"]["hard"]["recall"]["L2"],
                         [1, 2])
        rows = read(os.path.join(tmp, "audit.md")).split("\n")
        self.assertTrue([row for row in rows if row.startswith("| %s | 1 |"
                                                                % case_of("l2-two-faults"))
                         and "finding 2: stats.py + term 'in place'" in row])

    def test_one_tier_reports_as_before(self):
        base = self.folder({"l1-off-by-one.txt": answer("PASS")})
        lines, totals = score.report(score.runs_from_folder(base, KEYS), KEYS)
        self.assertNotIn("tiers", totals)
        self.assertFalse([line for line in lines if "over-blocking" in line
                          or line.startswith("tier ")])
        hard = self.folder({"l2-late-binding.txt": answer("PASS")})
        lines, totals = score.report(score.runs_from_folder(hard, KEYS), KEYS)
        self.assertNotIn("tiers", totals)
        self.assertIn("over-blocking nit: 0/0", lines)
        self.assertIn("recall: L1 0/0, L2 0/1 (0%), L3 0/0, L4 0/0, guard 0/0, all 0/1 (0%)",
                      lines)


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
                     "--no-publish", "--keep-temp",
                     "--allow-tools Agent Bash ToolSearch --model sonnet",
                     "--runs 1", "-j 1", "--max-cost-usd 15", "--output-dir "):
            self.assertIn(part, text)
        self.assertNotIn("--case", run)
        repo = os.path.dirname(os.path.dirname(PLUGIN))
        self.assertEqual(run[run.index("--output-dir") + 1], os.path.join(repo, "evals-results",
                                                                          "T"))
        self.assertEqual(score_command[-1], os.path.join(repo, "evals-results", "T",
                                                         "aggregate-result.json"))
        self.assertEqual(score.KEYS, os.path.join(repo, "evals-keys", CALIBRATION))
        self.assertNotIn("--trust-plugin", run)
        ignored = read(os.path.join(repo, ".gitignore")).split("\n") if os.path.isfile(
            os.path.join(repo, ".gitignore")) else ["evals-results/"]
        self.assertIn("evals-results/", ignored)
        self.assertEqual(self.command("--max-cost-usd", "1", "--trust-plugin")[0][-1],
                         "--trust-plugin")
        run = self.command("--max-cost-usd", "2.5", "--model", "opus", "--runs", "3", "-j",
                           "2", "--case", "rc-0?")[0]
        self.assertIn("--model opus --runs 3 -j 2 --max-cost-usd 2.5", " ".join(run))
        self.assertEqual(run[-2:], ["--case", "rc-0?"])

    def test_a_ceiling_is_required_and_bad_values_refused(self):
        for argv in ([], ["--max-cost-usd", "0"], ["--max-cost-usd", "x"],
                     ["--max-cost-usd", "5", "--model", "haiku"],
                     ["--max-cost-usd", "5", "--runs", "0"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                    runner.parser().parse_args(argv)
        with self.assertRaises(SystemExit):
            self.command("--max-cost-usd", "5", "-j", "9")

    def test_collect_copies_the_traces_and_removes_only_the_named_sandboxes(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, tmp, True)
        out = os.path.join(tmp, "results")
        os.makedirs(out)
        roots = []
        for number in (1, 2):
            root = os.path.join(tmp, "claude-eval-AB%d" % number)
            os.makedirs(os.path.join(root, "out"))
            os.makedirs(os.path.join(root, "work", "closed"))
            with open(os.path.join(root, "out", "trace.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("trace %d\n" % number)
            with open(os.path.join(root, "work", "object"), "w", encoding="utf-8") as fh:
                fh.write("read-only, as git writes its objects\n")
            os.chmod(os.path.join(root, "work", "object"), 0o400)
            os.chmod(os.path.join(root, "work", "closed"), 0o500)
            roots.append(root)
        other = os.path.join(tmp, "claude-eval-OTHER")
        os.makedirs(os.path.join(other, "out"))
        plain = os.path.join(tmp, "plain", "out")
        os.makedirs(plain)
        with open(os.path.join(plain, "trace.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("plain\n")
        runs = [{"tracePath": os.path.join(roots[0], "out", "trace.jsonl")},
                {"tracePath": os.path.join(roots[1], "out", "trace.jsonl")},
                {"tracePath": os.path.join(plain, "trace.jsonl")},
                {"tracePath": os.path.join(tmp, "claude-eval-GONE", "out", "trace.jsonl")}]
        path = write_result(out, runs, "rc-01")
        self.assertEqual(runner.collect(path), roots)
        data = json.loads(read(path))["cases"][0]["arms"]["with"]
        self.assertEqual([run["tracePath"] for run in data[:3]],
                         ["traces/rc-01-1.jsonl", "traces/rc-01-2.jsonl", "traces/rc-01-3.jsonl"])
        self.assertEqual(data[0]["keptTracePath"], runs[0]["tracePath"])
        self.assertEqual(data[3]["tracePath"], runs[3]["tracePath"])
        self.assertEqual(read(os.path.join(out, "traces", "rc-01-2.jsonl")), "trace 2\n")
        self.assertFalse([root for root in roots if os.path.exists(root)])
        self.assertTrue(os.path.isdir(other), "a sandbox the result does not name stays")
        self.assertTrue(os.path.isfile(os.path.join(plain, "trace.jsonl")),
                        "a folder not named like a sandbox stays")

    def test_home_falls_back_to_the_user_folder(self):
        seen = []
        with mock.patch.dict(os.environ, {"HOME": ""}), \
                mock.patch.object(runner.os.path, "expanduser", return_value="/u/me"), \
                mock.patch.object(runner, "preflight",
                                  side_effect=lambda r, t, h: seen.append(h) or ([], [])), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--max-cost-usd", "1", "--dry-run"]), 0)
        self.assertEqual(seen, ["/u/me"])

    def test_preflight(self):
        blind = runner.blind_pattern()
        self.assertTrue(blind.search("/x/evals-keys/y"))
        home = os.path.join(os.sep, "home", "me")
        self.assertEqual(runner.preflight(os.path.join(home, "repo"), os.path.join(os.sep, "tmp"),
                                          home), ([], []))
        errors, warnings = runner.preflight(os.path.join(os.sep, "srv", "repo"),
                                            os.path.join(os.sep, "tmp"), home)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("not under $HOME", warnings[0])
        for repo, temp in ((os.path.join(home, "reviewer-calibration"), "/tmp"),
                           (os.path.join(home, "repo"), "/tmp/evals-results")):
            errors = runner.preflight(repo, temp, home)[0]
            self.assertEqual(len(errors), 1, (repo, temp))
            self.assertIn("blind grader", errors[0])

    def test_the_exit_code_is_the_eval_s_or_score_s(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for eval_code, score_code, expected in ((0, 0, 0), (1, 0, 1), (0, 1, 1), (2, 1, 1)):
            def call(command, eval_code=eval_code, score_code=score_code):
                if command[0] == "claude":
                    out = command[command.index("--output-dir") + 1]
                    os.makedirs(out)
                    write_result(out, [])
                    return eval_code
                return score_code
            with self.subTest(eval=eval_code, score=score_code), \
                    mock.patch.object(runner, "REPO", os.path.join(tmp, str(expected),
                                                                   str(eval_code))), \
                    mock.patch.object(runner.subprocess, "call", side_effect=call), \
                    mock.patch.object(runner.sys, "platform", "linux"), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(["--max-cost-usd", "1"]), expected)
        with mock.patch.object(runner.sys, "platform", "win32"), \
                mock.patch.object(runner.subprocess, "call") as call, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(runner.main(["--max-cost-usd", "1"]), 2)
        call.assert_not_called()
        self.assertIn("Windows has no Bash sandbox", err.getvalue())
        with mock.patch.object(runner, "REPO", os.path.join(tmp, "evals-keys")), \
                mock.patch.object(runner.subprocess, "call") as call, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(runner.main(["--max-cost-usd", "1"]), 2)
        call.assert_not_called()
        self.assertIn("refused", err.getvalue())

    def test_dry_run_runs_nothing(self):
        done = subprocess.run([sys.executable, os.path.join(SUITE, "run.py"), "--dry-run",
                               "--max-cost-usd", "15"], capture_output=True,
                              env=dict(os.environ, PATH="", PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("claude plugin eval "))
        self.assertIn(" --tag reviewer-calibration --ablation ", lines[0])
        done = subprocess.run([sys.executable, os.path.join(SUITE, "run.py"), "--dry-run",
                               "--tier", "hard", "--max-cost-usd", "1"], capture_output=True,
                              env=dict(os.environ, PATH="", PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn(" --tag reviewer-calibration-hard --ablation ", lines[0])
        self.assertIn(" --max-cost-usd 1 ", lines[0])

    def test_the_tier_picks_the_tag(self):
        for argv, tag in (([], "reviewer-calibration"),
                          (["--tier", "base"], "reviewer-calibration"),
                          (["--tier", "hard"], "reviewer-calibration-hard")):
            with self.subTest(argv=argv):
                run = self.command("--max-cost-usd", "1", *argv)[0]
                self.assertEqual(run.count("--tag"), 1)
                self.assertEqual(run[run.index("--tag") + 1], tag)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            runner.parser().parse_args(["--max-cost-usd", "1", "--tier", "all"])


class ReadmeTest(unittest.TestCase):
    """The README's command for the invariant cases leaves this suite out; it names this one,
    where its keys and results live, and its limits."""

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
        self.assertIn("`evals-keys/reviewer-calibration/<case>.json` at the repository root",
                      self.text)
        self.assertIn("`evals-results/<UTC time>/` at the repository root", self.text)

    def test_trust_and_the_residual_risk(self):
        self.assertIn("add `--trust-plugin` when you start it from a session or a script",
                      self.text)
        self.assertIn("It does not run on Windows (run.py refuses)", self.text)
        self.assertIn("Limits, from a static reading of the 2.1.332 sandbox builder, not from an "
                      "observed run", self.text)
        self.assertIn("The residual risk is a checkout outside your home and outside the temp "
                      "folder", self.text)
        self.assertIn("run.py passes `--keep-temp`", self.text)
        self.assertIn("read a run's numbers, the pilot's first, together with its audit",
                      self.text)

    def test_no_mapping_in_the_readme(self):
        section = self.text.split("### Reviewer calibration")[1]
        for name in NAMES:
            self.assertNotIn("rc-" + name, section)
        self.assertEqual(sorted(set(re.findall(r"rc-[0-9]{2}", section))),
                         ["rc-01", "rc-20", "rc-21", "rc-32"])

    def test_the_hard_tier(self):
        self.assertIn("python3 plugins/manager-plugin/evals/reviewer-calibration/run.py "
                      "--tier hard", self.text)
        self.assertIn("`rc-21` to `rc-32` (tag `reviewer-calibration-hard`)", self.text)
        self.assertIn("a meaningful read needs `--runs 3`", self.text)
        self.assertIn("not a measurement", self.text)


if __name__ == "__main__":
    unittest.main()
