"""Tests for plan.py, on the shape of the living-plan template, on this repository's own plan and
on malformed plans: python3 -m unittest discover -s <this folder>"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import plan  # noqa: E402

SCRIPT = os.path.join(HERE, "plan.py")
TEMPLATE = os.path.join(HERE, "..", "references", "plan-template.md")
OWN_PLAN = os.path.join(HERE, "..", "..", "..", "..", "..", "docs", "LIVING_PLAN.md")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
NO_PHASE = "error: no phase: no `### <id>. <title>` heading under `## Phases`\n"
MISSING = "error: %s: no `%s:` line, or nothing after it\n"
SAME = "warning: %s and %s name the same path in Scope and neither depends on the other: %s\n"
NO_SECTION = "plan.py: no `### %s.` section in the plan on standard input\n"


def run(*args, text="", cwd=None):
    """(exit code, standard output, standard error) of plan.py, the plan on standard input."""
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    p = subprocess.run([sys.executable, SCRIPT] + list(args), input=data, capture_output=True,
                       env=ENV, cwd=cwd)
    return (p.returncode, p.stdout.decode("utf-8", "surrogateescape"),
            p.stderr.decode("utf-8", "surrogateescape"))


def phase(name, depends="none", scope=None, status="todo", without=()):
    """A phase's section as the template shapes it, without the labels named."""
    rows = (("Status", status), ("Objective", "one deliverable"),
            ("Scope", scope or "src/%s.py" % name.lower()), ("Depends on", depends),
            ("Risk", "standard"), ("Acceptance", "an observable result"),
            ("Validation", "standard"))
    return "### %s. The title of %s\n%s\n" % (
        name, name, "".join("%s: %s\n" % row for row in rows if row[0] not in without))


def a_plan(*phases):
    return ("# Plan\n\n## Constraints and project rules\n- Validation: `make test`\n\n"
            "## Phases\n\nFix-round limit per phase: 5\n\n" + "".join(phases)
            + "## Change log\n- created\n")


def check(*phases):
    code, out, err = run("check", text=a_plan(*phases))
    assert err == "", err
    return code, out


class TemplateShapeTest(unittest.TestCase):
    """A plan in the shape of `references/plan-template.md`."""

    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            self.template = fh.read().split("```markdown\n")[1].split("\n```")[0] + "\n"
        depends = 'Depends on: <phase ids or "none" — required; the manager schedules by it>\n'
        second = "### P2. <title>\n...\n"
        for placeholder in (depends, second):
            self.assertEqual(self.template.count(placeholder), 1, placeholder)
        self.plan = (self.template.replace(depends, "Depends on: none\n")
                     .replace(second, phase("P2", "P1") + phase("P10", "P1, P2").rstrip("\n")
                              + "\n"))

    def part(self, start, end):
        """The plan from the line that starts with `start` up to the one that starts with `end`."""
        return self.plan[self.plan.index("\n" + start) + 1:self.plan.index("\n" + end) + 1]

    def test_check_accepts_the_template_filled_in(self):
        self.assertEqual(run("check", text=self.plan), (0, "ok: 3 phases\n", ""))

    def test_check_reports_the_placeholders_left_in(self):
        code, out, err = run("check", text=self.template)
        self.assertEqual((code, err), (1, ""))
        for label in plan.REQUIRED:
            self.assertIn(MISSING % ("P2", label), out)
        self.assertIn('error: P1: no such phase in `Depends on`: <phase, ids, or, "none", —, '
                      'required, the, manager, schedules, by, it>\n', out)
        self.assertEqual(out.count("\n"), 1 + len(plan.REQUIRED))
        for line in out.splitlines():
            self.assertTrue(line.startswith("error: "), line)

    def test_phase_prints_the_section_and_what_binds_it(self):
        head = self.part("## Constraints", "### P1.")
        decisions = self.part("## Open owner decisions", "## Decided")
        for kept in ("## Constraints and project rules\n- Rules: ", "## Model strategy\n",
                     "## Binding decisions\n- B1. <decision>",
                     "## Phases\n\nStatus values: `todo` ", "Fix-round limit per phase: 5\n\n"):
            self.assertIn(kept, head)
        self.assertTrue(head.endswith("Fix-round limit per phase: 5\n\n"), head[-60:])
        self.assertTrue(decisions.startswith("## Open owner decisions\n\n### D1. <question>\n"))
        self.assertTrue(decisions.endswith("Raised: <date>\n\n"), decisions[-60:])
        first = self.part("### P1.", "### P2.")
        self.assertTrue(first.startswith("### P1. <title>\nStatus: todo\n"))
        self.assertIn("\nNotes: <decisions cited (B1, D2)", first)
        self.assertEqual(run("phase", "P1", text=self.plan), (0, head + first + decisions, ""))
        self.assertEqual(run("phase", "P2", text=self.plan),
                         (0, head + self.part("### P2.", "### P10.") + decisions, ""))
        tenth = self.part("### P10.", "## Decided")  # the last phase, then the open decisions
        self.assertEqual(run("phase", "P10", text=self.plan), (0, head + tenth, ""))
        for dropped in ("# <Project>", "## Goal", "## Done means", "## Scope", "## Decided",
                        "## Notes carried forward", "## Change log", "## How to keep"):
            self.assertIn("\n" + dropped, "\n" + self.plan)
            self.assertNotIn(dropped, head + first + tenth)

    def test_phase_without_a_section_for_the_id(self):
        """A plan-only PR's phase id, a phase the plan doesn't have, another id's prefix: the rest
        is printed, with exit code 1 and a line on standard error."""
        rest = (self.part("## Constraints", "### P1.")
                + self.part("## Open owner decisions", "## Decided"))
        for name in ("plan", "P3", "P", "P1."):
            self.assertEqual(run("phase", name, text=self.plan), (1, rest, NO_SECTION % name))
        self.assertEqual(run("phase", "P1", text=""), (1, "", NO_SECTION % "P1"))


class OwnPlanTest(unittest.TestCase):
    """The plan this repository is driven from; an installed copy of the plugin has none."""

    def setUp(self):
        if not os.path.isfile(OWN_PLAN):
            self.skipTest("no docs/LIVING_PLAN.md beside this plugin copy")
        with open(OWN_PLAN, encoding="utf-8", newline="") as fh:
            self.plan = fh.read()
        self.phases = re.findall(r"(?m)^### (P\d+)\. .+$", self.plan)
        self.assertGreaterEqual(len(self.phases), 2)

    def test_check(self):
        code, out, err = run("check", text=self.plan)
        self.assertEqual((code, err), (0, ""), out)
        lines = out.splitlines()
        self.assertEqual(lines[-1], "ok: %d phases" % len(self.phases))
        for line in lines[:-1]:
            self.assertTrue(line.startswith("warning: "), line)

    def test_phase(self):
        for name in self.phases:
            expected = []
            for section in re.split(r"(?m)^(?=## )", self.plan):
                if section.startswith(plan.PRINTED):
                    expected.append(section)
                elif section.startswith("## Phases"):
                    parts = re.split(r"(?m)^(?=### )", section)
                    expected.append(parts[0])
                    expected += [part for part in parts[1:] if part.startswith("### %s." % name)]
            expected = "".join(expected)
            self.assertEqual(run("phase", name, text=self.plan), (0, expected, ""), name)
            self.assertEqual(len(re.findall(r"(?m)^### ", expected)), 1, name)
            for heading in ("## Constraints", "## Binding decisions", "## Phases\n",
                            "Fix-round limit per phase:", "\nStatus: ", "\nAcceptance: "):
                self.assertIn(heading, expected, name)
            self.assertLess(len(expected.split()), len(self.plan.split()) * 0.5, name)


class MalformedPlanTest(unittest.TestCase):
    """What `check` reports: one `error:` line per problem and exit code 1."""

    def test_a_plan_in_order(self):
        self.assertEqual(check(phase("P1")), (0, "ok: 1 phase\n"))
        self.assertEqual(check(phase("P1"), phase("P2", "P1"), phase("P3", "P1, P2")),
                         (0, "ok: 3 phases\n"))

    def test_a_phase_id_used_twice(self):
        text = a_plan(phase("P1"), phase("P2"), phase("P1", scope="src/again.py"))
        first, second = [number for number, line in enumerate(text.split("\n"), 1)
                         if line.startswith("### P1.")]
        self.assertEqual(run("check", text=text),
                         (1, "error: line %d: phase P1 is already at line %d\n" % (second, first),
                          ""))

    def test_a_dependency_that_is_no_phase(self):
        for depends, wrong in (("P1, P7", "P7"), ("none, P1", "none"), ("p1", "p1"),
                               ("P1 — for its reader", "—, for, its, reader"),
                               ("P1, P8 and P9 (later)", "P8, P9")):
            self.assertEqual(check(phase("P1"), phase("P2", depends)),
                             (1, "error: P2: no such phase in `Depends on`: %s\n" % wrong),
                             depends)

    def test_a_dependency_cycle(self):
        self.assertEqual(check(phase("P1", "P3"), phase("P2", "P1"), phase("P3", "P2"),
                               phase("P4", "P3"), phase("P5")),
                         (1, "error: dependency cycle through P1, P2, P3\n"))
        self.assertEqual(check(phase("P1"), phase("P2", "P2")),
                         (1, "error: dependency cycle through P2\n"))

    def test_a_phase_without_one_of_its_lines(self):
        for label in plan.REQUIRED:
            self.assertEqual(check(phase("P1", without=(label,)), phase("P2", "P1")),
                             (1, MISSING % ("P1", label)), label)
        self.assertEqual(plan.REQUIRED, ("Status", "Objective", "Scope", "Depends on", "Risk",
                                         "Acceptance", "Validation"))
        self.assertEqual(check(phase("P1", status=""), phase("P2", "")),
                         (1, MISSING % ("P1", "Status") + MISSING % ("P2", "Depends on")))
        self.assertEqual(check(phase("P1"), "### P2. A title and nothing else\n\n"),
                         (1, "".join(MISSING % ("P2", label) for label in plan.REQUIRED)))

    def test_a_heading_under_phases_that_is_no_phase(self):
        for heading in ("### Group two", "### P3 has no dot", "### Phase 3. An id with a space",
                        "### P1.1. An id with a dot", "### P3.No space", "### . No id"):
            text = a_plan(phase("P1"), heading + "\n\n", phase("P2", "P1"))
            number = text.split("\n").index(heading) + 1
            self.assertEqual(run("check", text=text),
                             (1, "error: line %d: `%s` is not `### <id>. <title>`\n"
                              % (number, heading), ""), heading)

    def test_no_phase(self):
        self.assertEqual(run("check", text=""), (1, NO_PHASE, ""))
        self.assertEqual(check(), (1, NO_PHASE))
        elsewhere = a_plan(phase("P1")).replace("## Phases\n", "## Roadmap\n")
        self.assertEqual(run("check", text=elsewhere), (1, NO_PHASE, ""))

    def test_one_line_per_problem_and_warnings_beside_them(self):
        code, out = check(phase("P1", scope="src/api/"), phase("P2", "P9", scope="src/api/"),
                          phase("P2"), phase("P3", without=("Risk", "Validation")))
        self.assertEqual(code, 1)
        self.assertEqual(sorted(re.sub(r"line \d+", "line N", line)
                                for line in out.splitlines()),
                         sorted(["error: line N: phase P2 is already at line N",
                                 "error: P2: no such phase in `Depends on`: P9",
                                 "error: P3: no `Risk:` line, or nothing after it",
                                 "error: P3: no `Validation:` line, or nothing after it",
                                 (SAME % ("P1", "P2", "src/api")).rstrip("\n")]))

    def test_depends_on_as_it_is_written(self):
        for depends in ("P1, P2, P3", "P1 P2 P3", "P1, P2 and P3", "P1 (its reader), P2; P3.",
                        "P1,\nP2, P3", "P1, P2,\n  P3 (the last one)"):
            code, out = check(phase("P1"), phase("P2"), phase("P3"),
                              phase("P4", depends, scope="src/p1.py, src/p2.py, src/p3.py"))
            self.assertEqual((code, out), (0, "ok: 4 phases\n"), depends)  # it depends on all
        for depends in ("none", "None", "none.", "none (it stands alone)"):
            self.assertEqual(check(phase("P1"), phase("P2", depends)), (0, "ok: 2 phases\n"),
                             depends)

    def test_a_value_runs_over_the_lines_below_it(self):
        listed = phase("P1", scope="the reader:\n- src/reader.py (its `read`)\n  and lib/\n\n"
                                   "A paragraph of its own, on docs/ and more.")
        self.assertIn("Scope: the reader:\n- src/reader.py (its `read`)\n  and lib/\n\n"
                      "A paragraph of its own, on docs/ and more.\nDepends on: none\n", listed)
        for scope, same in (("src/reader.py", "src/reader.py"), ("lib/tools.py", "lib"),
                            ("docs/guide.md", None)):  # the empty line ended P1's Scope
            warning = SAME % ("P1", "P2", same) if same else ""
            self.assertEqual(check(listed, phase("P2", scope=scope)),
                             (0, warning + "ok: 2 phases\n"), scope)
        twice = phase("P2", scope="src/p2.py") + "Status: done (PR #3)\nScope: src/reader.py\n\n"
        self.assertEqual(check(listed, twice), (0, "ok: 2 phases\n"))  # a label's first line


class ScopeOverlapTest(unittest.TestCase):
    """The warning: two phases that are not done, have no dependency between them and name the
    same path in Scope. It never changes the exit code."""

    def test_the_same_path(self):
        for one, other, same in (
                ("src/api/users.py and its tests", "docs, then `src/api/users.py`.",
                 "src/api/users.py"),
                ("src/api/", "src/api/users.py", "src/api"),
                ("(src/api/users.py)", "src/api", "src/api"),
                ("the code-map SKILL.md", "SKILL.md, README.md", "SKILL.md"),
                ("docs/a.md, src/b.py, lib/", "lib/c.py; src/b.py; docs/a.md",
                 "docs/a.md, lib, src/b.py")):
            self.assertEqual(check(phase("P1", scope=one), phase("P2", scope=other)),
                             (0, SAME % ("P1", "P2", same) + "ok: 2 phases\n"), one)

    def test_every_pair_is_named(self):
        shared = [phase(name, scope="src/shared.py") for name in ("P1", "P2", "P3")]
        self.assertEqual(check(*shared),
                         (0, "".join(SAME % (one, other, "src/shared.py") for one, other in
                                     (("P1", "P2"), ("P1", "P3"), ("P2", "P3")))
                          + "ok: 3 phases\n"))

    def test_no_warning(self):
        quiet = (0, "ok: 3 phases\n")
        for label, phases in (
                ("a dependency", (phase("P1", scope="src/a.py"), phase("P2", scope="src/b.py"),
                                  phase("P3", "P1", scope="src/a.py"))),
                ("a dependency through another phase",
                 (phase("P1", scope="src/a.py"), phase("P2", "P1"),
                  phase("P3", "P2", scope="src/a.py"))),
                ("one of them is done",
                 (phase("P1", scope="src/a.py", status="done (PR #4)"), phase("P2"),
                  phase("P3", scope="src/a.py"))),
                ("named as out of scope",
                 (phase("P1", scope="src/a.py. Out of scope: src/b.py"), phase("P2"),
                  phase("P3", scope="src/b.py"))),
                ("other paths", (phase("P1", scope="src/api.py"), phase("P2", scope="src/api"),
                                 phase("P3", scope="src/api_v2.py, lib/src/api.py"))),
                ("words that are no path",
                 (phase("P1", scope="e.g. the 0.8.x reader, v1.2 etc. (3.8+) <path> docs"),
                  phase("P2"),
                  phase("P3", scope="e.g. the 0.8.x reader, v1.2 etc. (3.8+) <path> docs")))):
            self.assertEqual(check(*phases), quiet, label)


class CommandLineTest(unittest.TestCase):
    """The plan comes from standard input only: `phase` (and `check`) take no path, so the plan
    read is the one piped in (`git show <base-sha>:<plan-path> | ...`), never a working tree's."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        os.makedirs(os.path.join(self.tmp, "docs"))
        self.path = os.path.join(self.tmp, "docs", "LIVING_PLAN.md")
        self.plan = a_plan(phase("P1"), phase("P2", "P1"))
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.plan)

    def test_no_path_argument(self):
        for args in (("phase", "P1", self.path), ("phase", "P1", "docs/LIVING_PLAN.md"),
                     ("check", self.path), ("phase",), ()):
            code, out, err = run(*args, text=self.plan, cwd=self.tmp)
            self.assertEqual((code, out), (2, ""), args)
            self.assertIn("usage: plan.py ", err)
        # a path where the id goes is an id: nothing is opened
        self.assertEqual(run("phase", self.path, text="", cwd=self.tmp),
                         (1, "", NO_SECTION % self.path))

    def test_the_working_tree_is_not_read(self):
        self.assertEqual(run("phase", "P1", text="", cwd=self.tmp), (1, "", NO_SECTION % "P1"))
        self.assertEqual(run("check", text="", cwd=self.tmp), (1, NO_PHASE, ""))
        other = a_plan(phase("P1", scope="the piped plan"))
        code, out, err = run("phase", "P1", text=other, cwd=self.tmp)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Scope: the piped plan\n", out)

    def test_lines_are_printed_as_they_are(self):
        data = self.plan.replace("one deliverable", "çıktı — one → two", 1).encode("utf-8")
        data = data.replace(b"\n", b"\r\n").replace(b"an observable result", b"not \xff UTF-8", 1)
        code, out, err = run("phase", "P1", text=data)
        self.assertEqual((code, err), (0, ""))
        start, end = data.index(b"## Constraints"), data.index(b"### P2.")
        self.assertEqual(out.encode("utf-8", "surrogateescape"), data[start:end])
        self.assertIn(b"\xc3\xa7\xc4\xb1kt\xc4\xb1 \xe2\x80\x94 one \xe2\x86\x92 two\r\n",
                      data[start:end])
        self.assertEqual(run("check", text=data), (0, "ok: 2 phases\n", ""))
        unended = a_plan(phase("P1")).split("## Change log")[0].rstrip("\n")
        self.assertTrue(unended.endswith("Validation: standard"))
        self.assertEqual(run("phase", "P1", text=unended)[1],
                         unended[unended.index("## Constraints"):] + "\n")

    def test_nothing_is_written(self):
        before = sorted(os.listdir(HERE)), sorted(os.listdir(self.tmp))
        run("check", text=self.plan, cwd=self.tmp)
        run("phase", "P1", text=self.plan, cwd=self.tmp)
        self.assertEqual((sorted(os.listdir(HERE)), sorted(os.listdir(self.tmp))), before)


if __name__ == "__main__":
    unittest.main()
