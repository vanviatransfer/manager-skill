"""Tests for skilltrain.py: python3 -m unittest discover -s <this folder>"""
import contextlib
import io
import os
import sys
import tempfile
import re
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltrain  # noqa: E402

SKILL = """---
name: release-notes
description: Write the release notes for a tagged release. Not for changelogs of single PRs.
disable-model-invocation: true
---
<!-- self-training-skill v1 -->

# Release notes

The project rules and the living plan win over this skill; in a manager phase, the brief wins.

## Purpose

Write the release notes for one release.

## Steps

1. List the merged PRs since the last tag.
2. Group them by area.

## Rules

- Lead with user-visible changes. (L1)
- Name breaking changes first, with the
  migration step. (L2, L3)
- Keep it under one page. (owner: "kısa tut", 2026-11-01)

## Knowledge

- `docs/vault/releases.md`

## Record

Records: `docs/vault/skills/release-notes/records.md`

After each use, append exactly one row; never edit earlier rows:
`| <YYYY-MM-DD> | phase <id> or owner session | <outcome> | <tags> | <note> |`

## Changelog

- v1 2026-11-01: created — evidence: L1, L2, L3
"""

RECORDS = """# release-notes records

| date | context | outcome | tags | note |
|---|---|---|---|---|
"""

LESSONS = """# release-notes lessons

| id | lesson | label | evidence | status |
|---|---|---|---|---|
| L1 | Readers look for user-visible changes first. | sourced | docs/vault/releases.md | active |
| L2 | Breaking changes need a migration step. | sourced | project rules | active |
| L3 | Breaking changes go first. | hypothesis | none yet | active |
"""

TRAINER = """---
name: release-notes-trainer
description: Record and compare the owner's reactions to release notes ("kaydet", "iyi oldu", "kötü oldu", "hangisi daha iyi"). Not for making it (release-notes).
---
<!-- self-training-trainer v1 -->

# Train release-notes

## Trains

Skill: `release-notes`
Records: `docs/vault/skills/release-notes/records.md`
Lessons: `.claude/skills/release-notes/lessons.md`

## Every use the owner reacts to

1. Append one row with the owner's words verbatim.

## Domain record fields

- `length=<words>`

## Next experiment

One variable at a time.

## Turning records into skill changes

Use the self-training-skills Train mode.
"""


REFS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")


def from_template(name, fill):
    """The template's markdown block, with its placeholders filled."""
    with open(os.path.join(REFS, name), encoding="utf-8") as fh:
        text = fh.read()
    block = re.search(r"```markdown\n(.*?)\n```\n", text, re.S).group(1) + "\n"
    for old, new in fill:
        block = block.replace(old, new)
    return block


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = skilltrain.main(list(argv))
    return code, out.getvalue() + err.getvalue()


class SkilltrainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.dir = os.path.join(self.root, ".claude", "skills", "release-notes")
        self.write(".claude/skills/release-notes/SKILL.md", SKILL)
        self.write(".claude/skills/release-notes/lessons.md", LESSONS)
        self.write("docs/vault/skills/release-notes/records.md", RECORDS)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text, newline="\n"):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline=newline) as fh:
            fh.write(text)

    def append(self, rel, text):
        with open(os.path.join(self.root, *rel.split("/")), "a", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(text)

    def rows(self, *rows):
        self.append("docs/vault/skills/release-notes/records.md",
                    "".join("| %s |\n" % " | ".join(r) for r in rows))

    def edit(self, old, new, rel=".claude/skills/release-notes/SKILL.md", text=SKILL):
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new))

    def check_fails(self, needle):
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)

    def test_good_skill_passes(self):
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("ok:", out)

    def test_templates_pass(self):
        records = "docs/vault/skills/sample/records.md"
        self.write(".claude/skills/sample/SKILL.md", from_template("skill-template.md", [
            ("<name>", "sample"), ("<YYYY-MM-DD>", "2026-11-01"), ("<seed lesson ids>", "L1"),
            ("<records path, relative to the repository root>", records)]))
        self.write(".claude/skills/sample/lessons.md", LESSONS.replace("| L3 |", "| L4 |"))
        self.write(records, RECORDS)
        sample = os.path.join(self.root, ".claude", "skills", "sample")
        code, out = run("check", sample)
        self.assertEqual(code, 0, out)
        self.write(".claude/skills/sample-trainer/SKILL.md", from_template(
            "trainer-template.md",
            [("<name>", "sample"), ("<the worker's records path>", records)]))
        code, out = run("check", sample + "-trainer")
        self.assertEqual(code, 0, out)
        self.assertIn("sample: not due (0 records since v1) [trainer: sample-trainer]",
                      run("due", self.root)[1])

    def test_unmarked_skill_is_skipped(self):
        self.edit("<!-- self-training-skill v1 -->\n", "")
        code, out = run("check", self.dir)
        self.assertEqual((code, out.strip()), (0, "not a self-training skill"))

    def test_bad_path(self):
        self.assertEqual(run("check", os.path.join(self.root, "nope"))[0], 2)
        other = os.path.join(self.root, "elsewhere")
        os.makedirs(other)
        self.assertEqual(run("check", other)[0], 2)

    def test_frontmatter_problems(self):
        self.edit("name: release-notes\n", "")
        self.check_fails("frontmatter lacks name")
        self.edit("Write the release notes for a tagged release.", "x" * 601)
        self.check_fails("description is")

    def test_missing_and_misordered_sections(self):
        self.edit("## Knowledge\n", "## Know\n")
        self.check_fails("missing section: ## Knowledge")
        moved = SKILL.replace("## Purpose\n\nWrite the release notes for one release.\n", "")
        moved = moved.replace("## Changelog", "## Purpose\n\nx\n\n## Changelog")
        self.write(".claude/skills/release-notes/SKILL.md", moved)
        self.check_fails("sections out of order: Steps, Rules")

    def test_body_too_long(self):
        self.edit("2. Group them by area.\n", "2. Group them by area.\n" + "\n" * 200)
        self.check_fails("body is")

    def test_records_problems(self):
        os.remove(os.path.join(self.root, "docs/vault/skills/release-notes/records.md"))
        self.check_fails("does not exist")
        self.write("docs/vault/skills/release-notes/records.md", "| date | outcome |\n|---|---|\n")
        self.check_fails("lacks the header")
        self.edit("Records: `docs/vault/skills/release-notes/records.md`", "Records: here")
        self.check_fails("names no records path")
        self.edit("docs/vault/skills/release-notes/records.md", "../outside.md")
        self.check_fails("not inside the repository")

    @unittest.skipUnless(hasattr(os, "symlink"), "no symlinks")
    def test_symlinked_records_refused(self):
        real = "docs/vault/skills/release-notes/real.md"
        self.write(real, RECORDS)
        link = os.path.join(self.root, *"docs/vault/skills/release-notes/records.md".split("/"))
        os.remove(link)
        try:
            os.symlink(os.path.join(self.root, *real.split("/")), link)
        except OSError:
            self.skipTest("symlinks not permitted")
        self.check_fails("symlink; refused")

    def test_lessons_problems(self):
        self.write(".claude/skills/release-notes/lessons.md", LESSONS.replace("| L3 |", "| L9 |"))
        self.check_fails("cites L3, which lessons.md lacks")
        self.write(".claude/skills/release-notes/lessons.md",
                   LESSONS.replace("none yet | active", "none yet | retired"))
        self.check_fails("cites L3, which is retired")
        self.write(".claude/skills/release-notes/lessons.md", "| id | lesson |\n|---|---|\n")
        self.check_fails("lessons: ")
        os.remove(os.path.join(self.dir, "lessons.md"))
        self.check_fails("lessons: ")

    def test_uncited_rule(self):
        self.edit("- Keep it under one page. (owner: \"kısa tut\", 2026-11-01)",
                  "- Keep it under one page.")
        self.check_fails("rule cites no lesson or owner quote")

    def test_changelog_problems(self):
        self.edit("- v1 2026-11-01: created", "- v1 1 Nov: created")
        self.check_fails("changelog line doesn't match")
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v2 2026-11-01: created — evidence: L1\n"
                  "- v2 2026-11-05: shorter — evidence: L3")
        self.check_fails("does not increase")

    def test_crlf(self):
        self.write(".claude/skills/release-notes/SKILL.md", SKILL, newline="\r\n")
        self.write(".claude/skills/release-notes/lessons.md", LESSONS, newline="\r\n")
        self.write("docs/vault/skills/release-notes/records.md", RECORDS +
                   "| 2026-11-02 | phase P3 | pass | tone | ok |\n", newline="\r\n")
        self.assertEqual(run("check", self.dir)[0], 0)
        code, out = run("stats", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("records: 1\n", out)

    def test_stats_counts(self):
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-10: lead with breaking changes — evidence: L3 — expect: fewer "
                  "breaking blockers — revert if: breaking blockers again")
        self.rows(("2026-11-02", "phase P3", "changes-required", "breaking, tone", "missed it"),
                  ("2026-11-04", "phase P4", "changes-required", "breaking", "again"),
                  ("2026-11-10", "phase P5", "pass", "tone", "ok"),
                  ("2026-11-11", "phase P6", "pending-review", "length", ""),
                  ("2026-11-12", "owner session", "owner-good", "tone", "\"güzel\""),
                  ("2026-11-12", "phase P4", "pass", "breaking", "resolved"))
        code, out = run("stats", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("records: 6\n", out)
        self.assertIn("last training: v2 2026-11-10\n", out)
        self.assertIn("records since (on or after 2026-11-10): 4\n", out)
        self.assertIn("outcomes since: pending-review 1, pass 2, owner-good 1\n", out)
        self.assertIn("top tags since: tone 2, breaking 1, length 1\n", out)
        self.assertIn("pending-review (resolve from git and GitHub): phase P6\n", out)
        self.assertIn("owner verdicts: 1 since, 1 in total\n", out)
        self.assertIn("expected effect v2 2026-11-10 (records: 2 before, 4 after): "
                      "breaking 2 before, 1 after\n", out)
        self.assertIn("training due: no\n", out)

    def test_stats_due(self):
        self.rows(*[("2026-11-0%d" % d, "phase P%d" % d, "pass", "x", "") for d in range(2, 7)])
        self.assertIn("training due: yes (5 records since", run("stats", self.dir)[1])
        self.write("docs/vault/skills/release-notes/records.md", RECORDS)
        self.rows(("2026-11-02", "phase P1", "failed", "lint", ""),
                  ("2026-11-03", "owner session", "owner-bad", "lint", ""))
        self.assertIn("tag lint 2 times with a bad outcome", run("stats", self.dir)[1])

    def test_due_reports(self):
        self.write(".claude/skills/plain/SKILL.md", "---\nname: plain\ndescription: x\n---\nhi\n")
        code, out = run("due", self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "release-notes: not due (0 records since v1)\n")
        self.rows(*[("2026-11-0%d" % d, "phase P%d" % d, "pass", "x", "") for d in range(2, 7)])
        self.assertIn("release-notes: training due (5 records", run("due", self.root)[1])
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        self.assertEqual(run("due", empty), (0, "no self-training skills\n"))

    def test_trainer_passes_and_is_listed(self):
        self.write(".claude/skills/release-notes-trainer/SKILL.md", TRAINER)
        code, out = run("check", os.path.join(self.root, ".claude/skills/release-notes-trainer"))
        self.assertEqual(code, 0, out)
        self.assertIn("(trainer)", out)
        self.assertIn("[trainer: release-notes-trainer]", run("due", self.root)[1])

    def test_trainer_names_missing_worker(self):
        self.write(".claude/skills/release-notes-trainer/SKILL.md",
                   TRAINER.replace("Skill: `release-notes`", "Skill: `missing`"))
        code, out = run("check", os.path.join(self.root, ".claude/skills/release-notes-trainer"))
        self.assertEqual(code, 1, out)
        self.assertIn("trained skill: .claude/skills/missing/SKILL.md does not exist", out)
        self.assertIn("trainer of missing, which is not a marked skill", run("due", self.root)[1])

    def test_trainer_problems(self):
        rel = ".claude/skills/release-notes-trainer/SKILL.md"
        tdir = os.path.join(self.root, ".claude/skills/release-notes-trainer")
        self.write(rel, TRAINER.replace("## Next experiment", "## Next"))
        self.assertIn("missing section: ## Next experiment", run("check", tdir)[1])
        self.write(rel, TRAINER.replace("lessons.md`", "nope.md`"))
        self.assertIn("lessons: .claude/skills/release-notes/nope.md does not exist",
                      run("check", tdir)[1])
        self.edit("<!-- self-training-skill v1 -->\n", "")
        self.write(rel, TRAINER)
        self.assertIn("is not a marked self-training skill", run("check", tdir)[1])


if __name__ == "__main__":
    unittest.main()
