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
                  "- v2 2026-11-10: lead with breaking changes — evidence: L3 — "
                  "records: 2 —\n"
                  "  expect: fewer breaking blockers — revert if: breaking blockers again")
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
        self.assertIn("records since (after record row 2): 4\n", out)
        self.assertIn("outcomes since: pending-review 1, pass 2, owner-good 1\n", out)
        self.assertIn("top tags since: tone 2, breaking 1, length 1\n", out)
        self.assertIn("pending-review (resolve from git and GitHub): phase P6\n", out)
        self.assertIn("owner verdicts: 1 since, 1 in total\n", out)
        self.assertIn("expected effect v2 2026-11-10 (records: 2 before, 4 after): "
                      "breaking 2 before, 1 after\n", out)
        self.assertIn("training due: no\n", out)

    def test_same_day_training_resets(self):
        # resolved rows keep the use's date; the training on 2026-11-12 consumed all 6 rows
        self.rows(*[("2026-11-1%d" % d, "phase P%d" % d, "changes-required", "lint", "")
                    for d in range(0, 3)])
        self.rows(*[("2026-11-1%d" % d, "phase P%d" % d, "pass", "lint", "resolved")
                    for d in range(0, 3)])
        self.assertIn("training due: yes", run("stats", self.dir)[1])
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-12: lint rule — evidence: L3 — records: 6 — expect: no lint "
                  "blockers — revert if: lint blockers again")
        self.assertEqual(run("check", self.dir)[0], 0)
        code, out = run("stats", self.dir)
        self.assertIn("records since (after record row 6): 0\n", out)
        self.assertIn("training due: no\n", out)
        self.assertIn("(records: 6 before, 0 after): lint 6 before, 0 after", out)
        self.rows(("2026-11-12", "phase P7", "pass", "tone", "same day, after the training"))
        self.assertIn("records since (after record row 6): 1\n", run("stats", self.dir)[1])
        self.assertIn("release-notes: not due (1 records since v2)", run("due", self.root)[1])

    def test_no_change_entry_resets(self):
        self.rows(*[("2026-11-0%d" % d, "phase P%d" % d, "pass", "x", "") for d in range(2, 7)])
        self.assertIn("training due: yes", run("stats", self.dir)[1])
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-07: no change — records: 5 — reason: owner declined")
        self.assertEqual(run("check", self.dir)[0], 0)
        self.assertIn("training due: no\n", run("stats", self.dir)[1])

    def test_records_count_checked(self):
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — records: 3 — evidence: L1, L2, L3")
        self.check_fails("but the records file has 0 rows")

    def test_fallback_is_strictly_after_the_date(self):
        self.rows(("2026-11-01", "phase P1", "pass", "x", "creation day"),
                  ("2026-11-02", "phase P2", "pass", "x", ""))
        out = run("stats", self.dir)[1]
        self.assertIn("records since (after 2026-11-01): 1\n", out)

    def test_wrapped_changelog(self):
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-05: shorter — evidence: L3 — records: 0 —\n"
                  "  expect: fewer tone tags\n"
                  "  — revert if: tone again")
        self.assertEqual(run("check", self.dir)[0], 0)
        self.assertIn("expected effect v2 2026-11-05", run("stats", self.dir)[1])
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n- v2 Nov 5\n  2026: x")
        self.check_fails("changelog line doesn't match")

    def test_bad_records_row(self):
        self.rows(("2026-11-02", "phase P1", "pass", "x", "ok"))
        self.append("docs/vault/skills/release-notes/records.md",
                    "| 2026-11-03 | phase P2 | pass | x | no trailing pipe\n")
        self.check_fails("records.md:6 is a row that doesn't parse")
        code, out = run("stats", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("records: 1\n", out)
        self.assertIn("skipped rows that don't parse: docs/vault/skills/release-notes/records.md:6",
                      out)

    def test_lines_after_the_table_are_reported(self):
        self.rows(("2026-11-02", "phase P1", "pass", "x", "ok"))
        self.append("docs/vault/skills/release-notes/records.md",
                    "2026-11-03 | phase P2 | pass | x | no leading pipe |\n\nA paragraph.\n"
                    "| 2026-11-04 | phase P3 | pass | x | after the paragraph |\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        for n in (6, 8, 9):
            self.assertIn("records.md:%d is a row that doesn't parse" % n, out)
        out = run("stats", self.dir)[1]
        self.assertIn("records: 1\n", out)
        self.assertIn("records.md:6, docs/vault/skills/release-notes/records.md:8, "
                      "docs/vault/skills/release-notes/records.md:9", out)

    def test_records_count_is_the_dash_segment(self):
        self.rows(*[("2026-11-0%d" % d, "phase P%d" % d, "pass", "x", "") for d in range(2, 5)])
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-05: keep records: 1 per use — evidence: L3 - records: 3 — "
                  "expect: x")
        self.assertIn("records since (after record row 3): 0\n", run("stats", self.dir)[1])
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n"
                  "- v2 2026-11-05: keep records: 1 per use — evidence: L3")
        self.assertIn("records since (after 2026-11-05): 0\n", run("stats", self.dir)[1])

    def test_stray_changelog_lines(self):
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n* v2 2026-11-05: star")
        self.check_fails("changelog line is not a '- v<n> <YYYY-MM-DD>: ...' entry")
        self.edit("- v1 2026-11-01: created — evidence: L1, L2, L3",
                  "- v1 2026-11-01: created — evidence: L1, L2, L3\n\nA stray paragraph.")
        self.check_fails("indented continuation: A stray paragraph.")

    def test_record_values_checked(self):
        self.rows(("2026-11-02", "phase P1", "passed", "x", ""),
                  ("2026-13-02", "phase P2", "pass", "x", ""),
                  ("2 Nov", "phase P3", "pass", "x", ""))
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("records.md:5 has an unknown outcome: passed", out)
        self.assertIn("records.md:6 has a date that isn't YYYY-MM-DD: 2026-13-02", out)
        self.assertIn("records.md:7 has a date that isn't YYYY-MM-DD: 2 Nov", out)

    def test_folded_description_is_measured(self):
        self.edit("description: Write the release notes for a tagged release. Not for changelogs "
                  "of single PRs.\n", "description: >\n" + ("  %s\n" % ("x" * 80)) * 8)
        self.check_fails("description is 647 characters")
        self.edit("description: Write the release notes for a tagged release. Not for changelogs "
                  "of single PRs.\n", "description: |\n  Write the notes.\n  Short.\n")
        self.assertEqual(run("check", self.dir)[0], 0)

    def test_rules_paragraphs_and_sub_bullets(self):
        self.edit("- Lead with user-visible changes. (L1)\n",
                  "These rules apply to every release.\n- Lead with user-visible changes. (L1)\n")
        self.check_fails("rule without a bullet/citation: These rules apply")
        self.edit("- Lead with user-visible changes. (L1)\n",
                  "- Lead with user-visible changes. (L1)\n  - features first\n"
                  "    and fixes after\n  - then docs\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)

    def test_sections_in_code_fences_dont_count(self):
        self.edit("2. Group them by area.\n",
                  "2. Group them by area.\n\n```markdown\n## Purpose\n## Changelog\n```\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)

    def test_bom_and_bullet_styles(self):
        text = SKILL.replace("- Lead with user-visible changes. (L1)",
                             "* Lead with user-visible changes. (L1)\n1. Numbered rule.")
        self.write(".claude/skills/release-notes/SKILL.md", "\ufeff" + text)
        self.check_fails("rule cites no lesson or owner quote: Numbered rule.")
        self.write(".claude/skills/release-notes/SKILL.md", "\ufeff" + SKILL)
        self.assertEqual(run("check", self.dir)[0], 0)

    def test_near_miss_marker_reported(self):
        self.edit("<!-- self-training-skill v1 -->", "<!-- self-training skill v1 -->")
        self.check_fails("the marker doesn't match")
        self.assertIn("release-notes: error: the marker doesn't match", run("due", self.root)[1])
        self.edit("<!-- self-training-skill v1 -->\n", "intro\n<!-- self-training-skill v1 -->\n")
        self.check_fails("the marker doesn't match")

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
