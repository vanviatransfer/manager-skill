"""Tests for skilltrain.py: python3 -m unittest discover -s <this folder>"""
import contextlib
import io
import os
import sys
import tempfile
import re
import shutil
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import portability  # noqa: E402  (in the plugin folder)
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

| id | lesson | label | evidence | status | confidence | last-confirmed |
|---|---|---|---|---|---|---|
| L1 | Readers look for user-visible changes first. | owner-reported | owner: "önce kullanıcı", 2026-11-01 | active | high | 2026-11-01 |
| L2 | Breaking changes need a migration step. | owner-reported | owner: "geçiş adımı", 2026-11-01 | active | high | 2026-11-01 |
| L3 | Breaking changes go first. | owner-reported | owner: "kırıcılar önce", 2026-11-01 | active | high | 2026-11-01 |
"""

# The table before 0.9.12: five columns, a sourced seed and a hypothesis.
OLD_LESSONS = """# release-notes lessons

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


class Fixture(unittest.TestCase):
    """The release-notes skill in a temporary repository; today is 2026-11-20."""

    def setUp(self):
        self._today = skilltrain.today
        skilltrain.today = lambda: skilltrain.datetime.date(2026, 11, 20)
        self.addCleanup(setattr, skilltrain, "today", self._today)
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        self.dir = os.path.join(self.root, ".claude", "skills", "release-notes")
        self.write(".claude/skills/release-notes/SKILL.md", SKILL)
        self.write(".claude/skills/release-notes/lessons.md", LESSONS)
        self.write("docs/vault/skills/release-notes/records.md", RECORDS)
        self.write("docs/vault/releases.md", "# Releases\n")

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


class SkilltrainTest(Fixture):
    def test_good_skill_passes(self):
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("ok:", out)

    def test_templates_pass(self):
        records = "docs/vault/skills/sample/records.md"
        self.write(".claude/skills/sample/SKILL.md", from_template("skill-template.md", [
            ("<name>", "sample"), ("<YYYY-MM-DD>", "2026-11-01"), ("<seed lesson ids>", "L1"),
            ("<records path, relative to the repository root>", records),
            ("<vault page, project path or references/<file>>", "docs/vault/releases.md")]))
        self.write(".claude/skills/sample/lessons.md", LESSONS.replace("| L3 |", "| L4 |"))
        self.write(records, RECORDS)
        sample = os.path.join(self.root, ".claude", "skills", "sample")
        code, out = run("check", sample)
        self.assertEqual(code, 0, out)
        self.assertIn("sample: not due (0 records since v1)\n", run("due", self.root)[1])

    def test_wrapped_rule_starting_with_a_number_is_not_a_sub_bullet(self):
        rules, stray = skilltrain.bullets(["- Keep the summary to at most",
                                           "  3. lines, as the owner asked. (L1)",
                                           "- Parent rule (L1)", "  - sub detail"])
        self.assertEqual(stray, [])
        self.assertEqual(rules[0], "Keep the summary to at most 3. lines, as the owner asked. (L1)")
        self.assertEqual(rules[1], "Parent rule (L1)")

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
                   LESSONS.replace("önce\", 2026-11-01 | active", "önce\", 2026-11-01 | retired"))
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

    def test_old_trainer_is_retired(self):
        retired = ("retired trainer (self-training-skills 0.9.3 dropped trainers): delete this "
                   "folder; its worker's Record section now holds its rules")
        rel = ".claude/skills/release-notes-trainer"
        self.write(rel + "/SKILL.md", TRAINER)
        tdir = os.path.join(self.root, rel)
        for action in ("check", "stats"):
            code, out = run(action, tdir)
            self.assertEqual((code, out), (1, "%s: %s\n" % (rel, retired)), action)
        code, out = run("due", self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "release-notes: not due (0 records since v1)\n"
                         "release-notes-trainer: %s\n" % retired)
        self.assertNotIn("[trainer:", out)
        self.assertEqual(run("check", self.dir)[0], 0)

    def test_reference_without_routing(self):
        self.write(".claude/skills/release-notes/references/style.md", "# Style\n")
        self.check_fails("references/style.md has no routing in ## Knowledge (a bullet "
                         "\"- `references/style.md` — read when ...\")")
        self.edit("- `docs/vault/releases.md`\n", "- `docs/vault/releases.md`\n"
                  "- `references/style.md` — read when wording a heading\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.edit("- `docs/vault/releases.md`\n", "- `docs/vault/releases.md`\n"
                  "- `.claude/skills/release-notes/references/style.md` — read when x\n")
        self.assertEqual(run("check", self.dir)[0], 0, "a repository-root path counts too")
        self.edit("- `docs/vault/releases.md`\n", "- `docs/vault/releases.md`\n"
                  "- `references/` — read when x\n")
        self.check_fails("references/style.md has no routing")

    def test_broken_routing_path(self):
        self.edit("- `docs/vault/releases.md`\n", "- `docs/vault/releases.md`\n"
                  "- `references/gone.md` — read when x\n"
                  "- `docs/vault/old.md#intro` — read when y\n"
                  "- prose without a path is no routing\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("knowledge routing points at a missing file: references/gone.md", out)
        self.assertIn("knowledge routing points at a missing file: docs/vault/old.md#intro", out)
        self.assertEqual(out.count("knowledge routing"), 2, out)
        self.edit("- `docs/vault/releases.md`\n", "- `../elsewhere.md` — read when x\n")
        self.check_fails("knowledge routing points outside the repository: ../elsewhere.md")

    def test_backticked_text_that_is_no_path_is_no_routing(self):
        self.edit("- `docs/vault/releases.md`\n", "- `docs/vault/releases.md`\n"
                  "- `codemap.py query release` — read when finding a file\n"
                  "- `https://example.com/guide.md` — read when x\n"
                  "- `docs/**/*.md` — read when y\n"
                  "- `docs/vault/release?.md` — read when y\n"
                  "- `<vault page>` — read when z\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.edit("- `docs/vault/releases.md`\n", "- `codemap.py query x` — read when x\n"
                  "- `docs/vault/gone.md` — read when y\n")
        self.check_fails("knowledge routing points at a missing file: docs/vault/gone.md")

    def test_query_terms(self):
        self.write(".claude/skills/release-notes/references/cmd.md", "never rm -rf here\n")
        code, out = run("query", self.root, "--", "-rf")
        self.assertEqual(code, 0, out)
        self.assertIn("release-notes: references/cmd.md:1: never rm -rf here", out)
        for term in ("", "   "):
            code, out = run("query", self.root, term)
            self.assertEqual(code, 2, term)
            self.assertIn("query needs a non-empty TERM", out)

    def test_skill_layout(self):
        self.assertEqual(skilltrain.skill_layout(self.root), [(
            ".claude/skills/release-notes", "docs/vault/skills/release-notes/records.md", False)])
        self.write(".claude/skills/release-notes/references/a.md", "x\n")
        self.assertTrue(skilltrain.skill_layout(self.root)[0][2])

    def test_missing_lesson_id(self):
        self.edit("- Lead with user-visible changes. (L1)", "- Lead with user-visible changes. (L7)")
        self.check_fails("rule cites L7, which lessons.md lacks")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false"] + list(args), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def commit_all(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x")

    def init_git(self):
        if not shutil.which("git"):
            self.skipTest("no git")
        self.git("init", "-q")

    def test_dropped_trigger_from_the_skill(self):
        self.init_git()
        quoted = ('description: "Write the release notes. Use for \\"sürüm notu\\", '
                  '\u201crelease notes\u201d or \\"changelog\\"."\n')
        self.edit("description: Write the release notes for a tagged release. Not for changelogs "
                  "of single PRs.\n", quoted)
        self.commit_all()
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        self.assertEqual(code, 0, out)
        self.edit("description: Write the release notes for a tagged release. Not for changelogs "
                  "of single PRs.\n", 'description: Write the release notes. Use for '
                  '"sürüm notu" or "release notes".\n')
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        self.assertEqual(code, 1, out)
        self.assertEqual(out, ".claude/skills/release-notes: description dropped the trigger "
                         "\"changelog\" (from the skill's description at HEAD: "
                         ".claude/skills/release-notes/SKILL.md)\n")

    def test_dropped_trigger_from_the_retired_trainer(self):
        self.init_git()
        self.write(".claude/skills/release-notes-trainer/SKILL.md", TRAINER)
        self.commit_all()
        shutil.rmtree(os.path.join(self.root, ".claude", "skills", "release-notes-trainer"))
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        self.assertEqual(code, 1, out)
        for phrase in ("kaydet", "iyi oldu", "kötü oldu", "hangisi daha iyi"):
            self.assertIn("description dropped the trigger \"%s\" (from the trainer's description "
                          "at HEAD: .claude/skills/release-notes-trainer/SKILL.md)" % phrase, out)
        self.edit("Not for changelogs of single PRs.", 'Use for "kaydet", "iyi oldu", '
                  '"kötü oldu" or "hangisi daha iyi".')
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        self.assertEqual(code, 0, out)

    def test_triggers_from_a_new_skill_or_a_bad_ref(self):
        self.init_git()
        self.write("README.md", "x\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "x")
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        self.assertEqual(code, 0, out)
        self.assertIn("note: .claude/skills/release-notes/SKILL.md is not in HEAD: a new skill, "
                      "no triggers to keep\n", out)
        code, out = run("check", self.dir, "--triggers-from", "no-such-branch")
        self.assertEqual(code, 2, out)
        self.assertIn("--triggers-from: no commit no-such-branch in", out)
        self.assertEqual(run("check", self.dir, "--triggers-from=-x")[0], 2)

    def test_triggers_from_outside_git(self):
        if not shutil.which("git"):
            self.skipTest("no git")
        code, out = run("check", self.dir, "--triggers-from", "HEAD")
        if "is not in a git repository" not in out:
            self.skipTest("the temp folder lies inside a git repository")
        self.assertEqual(code, 2, out)

    def test_query(self):
        self.rows(("2026-11-02", "phase P1", "pending-review", "breaking", "migration=yes"))
        self.write(".claude/skills/release-notes/lessons.md", OLD_LESSONS)  # still queried
        self.write(".claude/skills/release-notes/references/style.md", "Breaking first.\n")
        self.write(".claude/skills/plain/SKILL.md", "---\nname: plain\ndescription: breaking\n"
                   "---\nbreaking\n")
        code, out = run("query", self.root, "Breaking")
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertIn("release-notes: SKILL.md:24: - Name breaking changes first, with the", lines)
        self.assertIn("release-notes: references/style.md:1: Breaking first.", lines)
        self.assertIn("release-notes: lessons.md:6 L2: | L2 | Breaking changes need a migration "
                      "step. | sourced | project rules | active |", lines)
        self.assertIn("release-notes: lessons.md:7 L3: | L3 | Breaking changes go first. | "
                      "hypothesis | none yet | active |", lines)
        self.assertIn("release-notes: docs/vault/skills/release-notes/records.md:5: | 2026-11-02 "
                      "| phase P1 | pending-review | breaking | migration=yes |", lines)
        self.assertFalse([ln for ln in lines if ln.startswith("plain:")], "unmarked: not searched")
        code, out = run("query", self.root, "nowhere-to-be-found")
        self.assertEqual((code, out), (1, "no hits for nowhere-to-be-found in 1 marked skill\n"))
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        self.assertEqual(run("query", empty, "x"), (1, "no self-training skills\n"))
        self.assertEqual(run("query", os.path.join(self.root, "nope"), "x")[0], 2)

    def test_query_output_is_capped(self):
        self.write(".claude/skills/release-notes/references/long.md", "needle\n" * 70)
        code, out = run("query", self.root, "needle")
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertEqual(len(lines), 51)
        self.assertEqual(lines[-1], "(cut: 20 more hits; use a longer term)")
        self.write(".claude/skills/release-notes/references/long.md", "x" * 300 + "needle\n")
        line = run("query", self.root, "needle")[1].splitlines()[0]
        self.assertLess(len(line), 160)
        self.assertIn("needle", line)

    def test_rules_hint_is_idempotent(self):
        line = skilltrain.RULES_LINE
        self.assertEqual(run("rules-hint", self.root), (0, "AGENTS.md: unchanged\n"
                                                         "CLAUDE.md: created\n"))
        claude = os.path.join(self.root, "CLAUDE.md")
        with open(claude, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Project instructions\n\n%s\n"
                             % skilltrain.RULES_LINE_CREATED)
        self.assertEqual(run("rules-hint", self.root)[1], "AGENTS.md: unchanged\n"
                         "CLAUDE.md: unchanged\n")
        self.assertEqual(run("rules-hint", self.root, "--remove")[1], "AGENTS.md: unchanged\n"
                         "CLAUDE.md: removed (it created the file, and only its title was left)\n")
        self.assertFalse(os.path.exists(claude))
        run("rules-hint", self.root)
        self.append("CLAUDE.md", "\n- an owner rule\n")
        run("rules-hint", self.root, "--remove")
        with open(claude, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Project instructions\n\n\n- an owner rule\n",
                             "more than the title: the file stays")
        self.write("CLAUDE.md", "# Project instructions\n")
        run("rules-hint", self.root)
        run("rules-hint", self.root, "--remove")
        with open(claude, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Project instructions\n", "not created by it: kept")
        os.remove(claude)
        self.write("AGENTS.md", "# Agents\n\n- old wording %s\n" % skilltrain.RULES_MARK)
        self.write("CLAUDE.md", "# Rules\n\n@AGENTS.md\n")
        self.assertEqual(run("rules-hint", self.root)[1], "AGENTS.md: line written\n"
                         "CLAUDE.md: unchanged\n")
        with open(os.path.join(self.root, "AGENTS.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Agents\n\n%s\n" % line)
        self.assertEqual(run("rules-hint", self.root, "--remove")[1], "AGENTS.md: line removed\n"
                         "CLAUDE.md: unchanged\n")
        with open(os.path.join(self.root, "AGENTS.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Agents\n")
        self.write("CLAUDE.md", "# Rules\n")
        run("rules-hint", self.root)
        with open(claude, encoding="utf-8") as fh:
            self.assertEqual(fh.read().count(skilltrain.RULES_MARK), 1)
        run("rules-hint", self.root, "--remove")
        with open(claude, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Rules\n")

    def test_rules_hint_needs_marked_skills(self):
        self.edit("<!-- self-training-skill v1 -->\n", "")
        self.assertEqual(run("rules-hint", self.root),
                         (0, "no self-training skills: nothing written\n"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "CLAUDE.md")))

    def test_the_rules_line_is_the_skills_line(self):
        with open(os.path.join(os.path.dirname(REFS), "SKILL.md"), encoding="utf-8") as fh:
            skill = fh.read()
        self.assertTrue(skilltrain.RULES_LINE.split(" <!--")[0][2:] in skill, "not in SKILL.md")



LESSONS_FILE = ".claude/skills/release-notes/lessons.md"
TRAINED = ("- v1 2026-11-01: created — evidence: L1, L2, L3\n"
           "- v2 2026-11-10: no change — records: 0 — reason: owner declined")


class LessonEvidenceTest(Fixture):
    """0.9.12: a rule's lesson needs a verifier outcome; confidence, last-confirmed, staleness
    and the migration of the old five-column table."""

    def lessons(self, *rows, old=False):
        head = ("| id | lesson | label | evidence | status |\n|---|---|---|---|---|\n" if old else
                "| id | lesson | label | evidence | status | confidence | last-confirmed |\n"
                "|---|---|---|---|---|---|---|\n")
        self.write(LESSONS_FILE, "# lessons\n\n" + head +
                   "".join("| %s |\n" % " | ".join(r) for r in rows))

    def rules(self, text, changelog=None):
        new = SKILL.replace("- Lead with user-visible changes. (L1)\n- Name breaking changes "
                            "first, with the\n  migration step. (L2, L3)\n", text)
        if changelog:
            new = new.replace("- v1 2026-11-01: created — evidence: L1, L2, L3", changelog)
        self.write(".claude/skills/release-notes/SKILL.md", new)

    def test_old_and_new_tables_parse(self):
        sk = skilltrain.Skill(self.root, ".claude/skills/release-notes")
        new = skilltrain.load_lessons(sk)
        self.assertEqual((new["L1"]["confidence"], new["L1"]["confirmed"]), ("high", "2026-11-01"))
        self.assertFalse(sk.lessons_old)
        self.assertEqual(sk.notes, [])
        self.write(LESSONS_FILE, OLD_LESSONS)
        sk = skilltrain.Skill(self.root, ".claude/skills/release-notes")
        old = skilltrain.load_lessons(sk)
        self.assertTrue(sk.lessons_old)
        self.assertEqual({k: (v["confidence"], v["confirmed"]) for k, v in old.items()},
                         {k: ("low", "unknown") for k in ("L1", "L2", "L3")})
        self.rules("- Lead with user-visible changes. (L1, L2)\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)  # an old table is no error: one note
        self.assertEqual(out.count("has no confidence and last-confirmed columns"), 1, out)
        self.assertEqual(run("stats", self.dir)[1].count("has no confidence and last-confirmed"),
                         1)

    def test_bad_confidence_and_date_cells(self):
        self.lessons(("L1", "a", "owner-reported", 'owner: "x", 2026-11-01', "active", "sure",
                      "2026-11-01"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-11-01', "active", "high",
                      "Nov 1"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-11-01', "active", "high",
                      "unknown"))
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("L1 has confidence sure (one of high, medium, low)", out)
        self.assertIn("L2 has last-confirmed Nov 1 (YYYY-MM-DD or unknown)", out)
        self.assertNotIn("L3 has", out)

    def test_confidence_rules(self):
        rows = [["2026-11-02", "phase P3", "pass", "", ""],
                ["2026-11-04", "phase P4", "changes-required", "", ""],
                ["2026-11-05", "owner session", "owner-good", "", ""]]
        def conf(evidence):
            found, missing, owner = skilltrain.support(evidence, rows)
            return (skilltrain.confidence(found, owner), skilltrain.last_confirmed(found, owner),
                    missing)
        self.assertEqual(conf("docs/vault/releases.md"), ("low", "unknown", []))
        self.assertEqual(conf("2026-11-02 phase P3: pass"), ("medium", "2026-11-02", []))
        self.assertEqual(conf("2026-11-02 phase P3: pass; 2026-11-04 phase P4: changes-required"),
                         ("high", "2026-11-04", []))
        # the same use cited twice is one outcome, not two independent ones
        self.assertEqual(conf("2026-11-02 phase P3: pass, again 2026-11-02 phase P3: pass")[0],
                         "medium")
        self.assertEqual(conf("2026-11-05 owner session: owner-good"),
                         ("high", "2026-11-05", []))
        self.assertEqual(conf('owner: "böyle kalsın", 2026-11-07'), ("high", "2026-11-07", []))
        self.assertEqual(conf("2026-11-03 phase P9: pass"),
                         ("low", "unknown", ["2026-11-03 phase P9: pass"]))

    def test_rule_citing_an_unverified_lesson_is_reported(self):
        self.rows(("2026-11-02", "phase P3", "pass", "breaking", "ok"))
        self.lessons(("L1", "a", "observed", "2 runs looked better", "active", "low", "unknown"),
                     ("L2", "b", "hypothesis", "2026-11-02 phase P3: pass", "active", "medium",
                      "2026-11-02"),
                     ("L3", "c", "observed", "2026-11-02 phase P3: pass", "active", "medium",
                      "2026-11-02"))
        self.rules("- Lead with user-visible changes. (L1)\n- Breaking first. (L2, L3)\n"
                   "- Again. (L1)\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("rule cites L1, whose evidence cites no verifier outcome"), 1)
        self.assertIn("rule cites L2, a hypothesis: a hypothesis never backs a rule", out)
        self.assertNotIn("rule cites L3", out)

    def test_cited_record_must_exist(self):
        self.lessons(("L1", "a", "observed", "2026-11-02 phase P3: pass", "active", "medium",
                      "2026-11-02"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-11-01', "active", "high",
                      "2026-11-01"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-11-01', "active", "high",
                      "2026-11-01"))
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("lessons: L1 cites 2026-11-02 phase P3: pass, which the records lack", out)
        self.assertEqual(out.count(" L1"), 1, out)  # one line for the lesson, none for its rule
        self.rows(("2026-11-02", "phase P3", "pass", "breaking", "ok"))
        self.assertEqual(run("check", self.dir)[0], 0)

    def test_sourced_seed_backs_a_rule_only_until_the_first_training(self):
        self.lessons(("L1", "a", "sourced", "docs/vault/releases.md", "active", "low", "unknown"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-11-01', "active", "high",
                      "2026-11-01"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-11-01', "active", "high",
                      "2026-11-01"))
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.rules("- Lead with user-visible changes. (L1)\n- Breaking first. (L2, L3)\n",
                   TRAINED)
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("rule cites L1, whose evidence cites no verifier outcome", out)

    def test_stale_by_days(self):
        self.lessons(("L1", "a", "owner-reported", 'owner: "x", 2026-08-01', "active", "high",
                      "2026-08-01"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-08-23', "active", "high",
                      "2026-08-23"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-01-01', "retired", "high",
                      "2026-01-01"))
        self.rules("- Lead with user-visible changes. (L1, L2)\n")
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)  # a flag, never a problem or a retirement
        self.assertIn("note: stale lesson L1 (last-confirmed 2026-08-01, 111 days ago, 0 uses "
                      "since): keep, re-confirm or retire it in the next training\n", out)
        self.assertNotIn("L2 (", out)  # 89 days
        self.assertNotIn("L3 (", out)  # not active
        self.assertIn("\nnote: stale lesson L1 (", run("stats", self.dir)[1])
        out = run("check", self.dir, "--stale-days", "200")[1]
        self.assertNotIn("stale", out)
        self.assertIn("stale lesson L2", run("check", self.dir, "--stale-days", "30")[1])
        with open(os.path.join(self.dir, "lessons.md"), encoding="utf-8") as fh:
            self.assertIn("| active | high | 2026-08-01 |", fh.read())  # untouched

    def test_stale_by_uses(self):
        self.lessons(("L1", "a", "owner-reported", 'owner: "x", 2026-11-01', "active", "high",
                      "2026-11-01"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-11-03', "active", "high",
                      "2026-11-03"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-11-01', "active", "high",
                      "unknown"))
        self.rules("- Lead with user-visible changes. (L1, L2, L3)\n")
        self.rows(*[("2026-11-02", "phase P%d" % i, "pass", "", "") for i in range(2)])
        self.rows(*[("2026-11-04", "phase Q%d" % i, "pass", "", "") for i in range(20)])
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("note: stale lesson L1 (last-confirmed 2026-11-01, 19 days ago, 22 uses "
                      "since)", out)
        self.assertNotIn("L2 (", out)  # exactly 20 uses since: not more than 20
        self.assertIn("note: stale lesson L3 (last-confirmed unknown, 22 uses since)", out)
        stats = run("stats", self.dir)[1]
        self.assertEqual(stats.count("stale lesson"), 2, stats)
        self.assertIn("stale lesson L2", run("stats", self.dir, "--stale-uses", "19")[1])

    def test_no_stale_lines_when_nothing_is_flagged(self):
        code, out = run("stats", self.dir)
        self.assertEqual(code, 0, out)
        self.assertTrue(out.endswith("training due: no\n"), out)
        self.assertEqual(run("check", self.dir)[1], "ok: .claude/skills/release-notes (skill)\n")

    def test_stale_options_need_check_or_stats(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                skilltrain.main(["due", self.root, "--stale-days", "5"])
            with self.assertRaises(SystemExit):
                skilltrain.main(["stats", self.dir, "--migrate"])
            with self.assertRaises(SystemExit):
                skilltrain.main(["check", self.dir, "--stale-uses", "-1"])

    def test_migrate_keeps_every_other_byte(self):
        old = OLD_LESSONS.replace("| L1 | Readers", "| L1 |  Readers").replace(
            "| project rules | active |", "| 2026-11-02 phase P3: pass; 2026-11-05 owner "
            "session: owner-good | active |") + "\n"
        self.write(LESSONS_FILE, old, newline="\r\n")
        self.rows(("2026-11-02", "phase P3", "pass", "breaking", "ok"),
                  ("2026-11-05", "owner session", "owner-good", "", "\"iyi\""))
        self.rules("- Lead with user-visible changes. (L1, L2)\n")
        path = os.path.join(self.dir, "lessons.md")
        with open(path, "rb") as fh:
            before = fh.read()
        code, out = run("check", self.dir, "--migrate")
        self.assertEqual(code, 0, out)
        self.assertIn("migrated: .claude/skills/release-notes/lessons.md (3 rows", out)
        self.assertNotIn("has no confidence", out)
        with open(path, "rb") as fh:
            after = fh.read()
        b, a = before.split(b"\r\n"), after.split(b"\r\n")
        self.assertEqual(len(a), len(b))
        for x, y in zip(b, a):
            if x.startswith(b"|"):
                self.assertTrue(y.startswith(x), (x, y))  # every old cell byte-identical
            else:
                self.assertEqual(x, y)
        text = after.decode("utf-8")
        self.assertIn("| status | confidence | last-confirmed |\r\n|---|---|---|---|---|---|---|",
                      text)
        self.assertIn("|  Readers look for user-visible changes first. | sourced | "
                      "docs/vault/releases.md | active | low | unknown |\r\n", text)
        self.assertIn("owner-good | active | high | 2026-11-05 |\r\n", text)
        self.assertIn("| none yet | active | low | unknown |\r\n", text)
        sk = skilltrain.Skill(self.root, ".claude/skills/release-notes")
        self.assertEqual(skilltrain.load_lessons(sk)["L2"]["confidence"], "high")
        code, out = run("check", self.dir, "--migrate")
        self.assertEqual(code, 0, out)
        self.assertIn(".claude/skills/release-notes: lessons: .claude/skills/release-notes/"
                      "lessons.md already has the confidence and last-confirmed columns", out)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), after)

    def test_old_table_evidence_gaps_are_notes_until_migrated(self):
        self.rows(("2026-11-02", "phase P3", "pass", "breaking", "ok"))
        rows = (("L1", "a", "observed", "2 runs looked better", "active"),
                ("L2", "b", "observed", "2026-11-04 phase P9: pass", "active"),
                ("L3", "c", "hypothesis", "2026-11-02 phase P3: pass", "active"))
        self.rules("- Lead with user-visible changes. (L1, L2)\n", TRAINED)
        self.lessons(*rows, old=True)
        code, out = run("check", self.dir)
        self.assertEqual(code, 0, out)  # an old table: notes, not problems
        self.assertIn("note: rule cites L1, whose evidence cites no verifier outcome", out)
        self.assertIn("note: lessons: L2 cites 2026-11-04 phase P9: pass, which the records "
                      "lack", out)
        self.assertEqual(out.count(" L2"), 1, out)
        self.lessons(*[r + ("low", "unknown") for r in rows])
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)  # a migrated table: problems
        self.assertIn(".claude/skills/release-notes: rule cites L1, whose evidence cites no "
                      "verifier outcome", out)
        self.assertIn(".claude/skills/release-notes: lessons: L2 cites 2026-11-04 phase P9: "
                      "pass, which the records lack", out)
        self.assertNotIn("note: rule cites", out)
        for old in (True, False):  # a hypothesis is a problem in both
            self.rules("- Lead with user-visible changes. (L3)\n", TRAINED)
            self.lessons(*[r if old else r + ("medium", "2026-11-02") for r in rows], old=old)
            code, out = run("check", self.dir)
            self.assertEqual(code, 1, out)
            self.assertIn(".claude/skills/release-notes: rule cites L3, a hypothesis", out)

    def test_last_confirmed_after_today_is_a_problem(self):
        self.lessons(("L1", "a", "owner-reported", 'owner: "x", 2026-11-01', "active", "high",
                      "2026-11-21"),
                     ("L2", "b", "owner-reported", 'owner: "y", 2026-11-01', "active", "high",
                      "2026-11-20"),
                     ("L3", "c", "owner-reported", 'owner: "z", 2026-11-01', "active", "high",
                      "2026-11-01"))
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertIn("lessons: L1 has last-confirmed 2026-11-21, later than today (2026-11-20)",
                      out)
        self.assertNotIn("L2 has", out)  # today is fine

    def test_changelog_problems_keep_their_place(self):
        self.rules("- Lead with user-visible changes.\n", "- v1 1 Nov: created")
        code, out = run("check", self.dir)
        self.assertEqual(code, 1, out)
        self.assertLess(out.index("rule cites no lesson"), out.index("changelog line doesn't"))

    def test_migrate_splits_on_newlines_only_and_keeps_every_byte(self):
        odd = "a\u2028b\x85c\x0cd\x1ee"  # line breaks to str.splitlines, cell text here
        old = ("\ufeff# lessons \x0c\r\n\r\n| id | lesson | label | evidence | status |  \r\n"
               "|---|---|---|---|---|\t\n"
               "| L1 | %s | sourced | docs/vault/releases.md | active | \n"
               "| L2 | b | owner-reported | owner: \"x\", 2026-11-01 | active |\r\n"
               "\n| L3 | c | hypothesis | none | retired |" % odd)
        self.write(LESSONS_FILE, old)
        self.rules("- Lead with user-visible changes. (L2)\n")
        code, out = run("check", self.dir, "--migrate")
        self.assertEqual(code, 0, out)
        self.assertIn("(3 rows", out)
        with open(os.path.join(self.dir, "lessons.md"), "rb") as fh:
            after = fh.read().decode("utf-8")
        expected = ("\ufeff# lessons \x0c\r\n\r\n| id | lesson | label | evidence | status |"
                    " confidence | last-confirmed |  \r\n"
                    "|---|---|---|---|---|---|---|\t\n"
                    "| L1 | %s | sourced | docs/vault/releases.md | active | low | unknown | \n"
                    "| L2 | b | owner-reported | owner: \"x\", 2026-11-01 | active | high | "
                    "2026-11-01 |\r\n"
                    "\n| L3 | c | hypothesis | none | retired | low | unknown |" % odd)
        self.assertEqual(after, expected)

    def test_migrate_refuses_a_row_it_cant_split(self):
        self.write(LESSONS_FILE, OLD_LESSONS.replace("| none yet |", "| none | yet |"))
        code, out = run("check", self.dir, "--migrate")
        self.assertEqual(code, 1, out)
        self.assertIn("lessons.md:7 doesn't have exactly 5 cells", out)
        with open(os.path.join(self.dir, "lessons.md"), encoding="utf-8") as fh:
            self.assertIn("| id | lesson | label | evidence | status |\n|---|", fh.read())


if __name__ == "__main__":
    unittest.main()
