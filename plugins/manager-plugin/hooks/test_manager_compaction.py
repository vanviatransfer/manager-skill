"""Tests for what carries a manager run across a compaction: manager-run-compact.sh (the PreCompact
and SessionStart `compact` hook), the size ceilings of the manager texts, the manager skill's
pointers to its references and the step-0 commands in `references/establish-state.md`:
python3 -m unittest discover -s <this folder>"""
import glob
import json
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
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
from test_prefer_plugin_agents import ENV, MANAGER, SKILLS, command_in, snapshot  # noqa: E402

HOOK = os.path.join(HERE, "manager-run-compact.sh")
REFS = os.path.join(MANAGER, "references")
SESSION = "0f3c9a1e-5b7d-4c2a-9e1f-0123456789ab"
MARKER = "~/.claude/manager-runs/active/${CLAUDE_SESSION_ID}"
NOTES = "~/.claude/manager-runs/notes/${CLAUDE_SESSION_ID}.md"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def manager_texts():
    """{file name: text with single spaces} of the manager skill and its references."""
    paths = [os.path.join(MANAGER, "SKILL.md")] + sorted(glob.glob(os.path.join(REFS, "*.md")))
    return {os.path.basename(p): " ".join(read(p).split()) for p in paths}


class ManagerRunCompactHookTest(unittest.TestCase):
    """manager-run-compact.sh: speaks only while this session's run marker exists; silent, exit 0
    and nothing written everywhere else."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "my home")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.home)
        os.makedirs(os.path.join(self.repo, ".git"))
        self.env = dict(ENV, HOME=self.home)
        self.env.pop("CLAUDE_PLUGIN_ROOT", None)

    def mark(self, session=SESSION):
        """Write the run marker where the manager skill says, for this session id."""
        self.assertIn("`%s`" % MARKER, read(os.path.join(MANAGER, "SKILL.md")))
        path = MARKER.replace("~", self.home).replace("${CLAUDE_SESSION_ID}", session)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("R2026-01-01-0000\n")
        return path

    def notes(self, text, session=SESSION):
        """Write the run's notes file where the manager skill says, for this session id."""
        self.assertIn("`%s`" % NOTES, read(os.path.join(MANAGER, "SKILL.md")))
        path = NOTES.replace("~", self.home).replace("${CLAUDE_SESSION_ID}", session)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def hook(self, event, raw=None, args=None, env=None, **fields):
        payload = {"session_id": SESSION, "transcript_path": "/t/s.jsonl", "cwd": self.repo,
                   "hook_event_name": event}
        payload.update({"trigger": "auto", "custom_instructions": ""} if event == "PreCompact"
                       else {"source": "compact"})
        payload.update(fields)
        data = raw if raw is not None else json.dumps(payload)
        p = subprocess.run(["sh", HOOK] + ([event] if args is None else args),
                           input=data if isinstance(data, bytes) else data.encode(),
                           capture_output=True, env=env or self.env, cwd=self.repo)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")

    def assert_silent(self, event, **kw):
        self.assertEqual(self.hook(event, **kw), (0, "", ""), (event, kw))

    def test_without_a_run_marker_both_events_are_silent(self):
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)
        os.makedirs(os.path.join(self.home, ".claude", "manager-runs", "active"))
        with open(os.path.join(self.home, ".claude", "manager-runs", "2026-01-01.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("a run record is not a marker\n")
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)

    def test_pre_compact_keeps_the_working_notes_lines(self):
        self.mark()
        code, out, err = self.hook("PreCompact")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("manager-plugin: a manager run is in progress"))
        self.assertLess(len(out), 10000, "Claude Code cuts a hook's output at 10,000 characters")
        text = " ".join(out.split())
        self.assertIn("keep every working-notes line of the run verbatim", text)
        self.assertIn("re-read the manager skill", text)
        corpus = " ".join(manager_texts().values())
        spans = re.findall(r"`([^`]+)`", out)
        for line in ("Run <id>: model strategy ...", "Run <id>: code map ...", "Project rules",
                     "D<n> → <answer>: \"<owner's words>\"", "<phase>: rotated at round <k>",
                     "Risks:", "subagent_tokens"):
            self.assertIn(line, spans)
        for span in spans:  # the hook names only lines the skill really keeps
            self.assertIn(span.replace(" ...", ""), corpus, span)

    def test_session_start_prints_one_line(self):
        self.mark()
        code, out, err = self.hook("SessionStart")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("\n"), 1)
        self.assertTrue(out.endswith("\n"))
        self.assertTrue(out.startswith("manager-plugin: "))
        self.assertIn("re-read the manager skill", out)
        self.assertIn("every file in its references/ whose trigger applies", out)
        # A condition, never a statement: read as one, it ended a live run's notes.
        self.assertTrue(out.endswith(
            "(If no manager run is in progress any more, ignore this line and remove "
            "~/.claude/manager-runs/active/%s and ~/.claude/manager-runs/notes/%s.md.)\n"
            % (SESSION, SESSION)), out)
        self.assertNotIn("has ended", out)
        pretty = json.dumps({"session_id": SESSION, "cwd": self.repo, "source": "compact"},
                            indent=2)
        self.assertEqual(self.hook("SessionStart", raw=pretty), (code, out, err))

    def test_only_this_sessions_marker_counts(self):
        self.mark("another-session")
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)
            self.assertNotEqual(self.hook(event, session_id="another-session")[1], "")

    def test_the_run_ends_when_the_marker_is_removed(self):
        path = self.mark()
        self.assertNotEqual(self.hook("SessionStart")[1], "")
        os.remove(path)
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)

    def test_a_subagents_own_compaction_is_silent(self):
        self.mark()
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event, agent_id="a1b2c3", agent_type="manager-plugin:implementer")
            quoted = 'keep "agent_id": "x" and "session_id": "another-session" in the summary'
            self.assertNotEqual(self.hook(event, custom_instructions=quoted)[1], "",
                                "text inside a field is not the field")

    def test_errors_fail_open(self):
        self.mark()
        self.mark("x")
        for event in ("PreCompact", "SessionStart"):
            for raw in ("not json", "", "[]", "{", '{"session_id": 7}', '{"session_id": null}',
                        '{"session_id": ""}', '{"session_id": "../active/x"}',
                        '{"session_id": "a b"}', '{"session_id": "x/../x"}',
                        b'\xff\xfe {"session_id": "\xff"}'):
                self.assertEqual(self.hook(event, raw=raw), (0, "", ""), (event, raw))
            self.assert_silent(event, args=[])
            self.assert_silent(event, args=["Stop"])
            self.assert_silent(event, args=[event.lower()])
            self.assert_silent(event, env={k: v for k, v in self.env.items() if k != "HOME"})
            self.assert_silent(event, env=dict(self.env, HOME=""))
            self.assert_silent(event, env=dict(self.env, HOME=os.path.join(self.tmp, "nowhere")))
        os.makedirs(os.path.join(self.home, ".claude", "manager-runs", "active", "a-folder"))
        self.assert_silent("SessionStart", session_id="a-folder")

    def test_it_needs_only_sh_cat_grep_and_sed(self):
        self.mark()
        tools = os.path.join(self.tmp, "bin")
        os.makedirs(tools)
        for name in ("sh", "cat", "grep", "sed"):
            found = shutil.which(name)
            if not found or not hasattr(os, "symlink"):
                self.skipTest("needs sh, cat, grep, sed and symlinks")
            portability.symlink(self, found, os.path.join(tools, name))
        self.env["PATH"] = tools
        self.assertEqual(self.hook("SessionStart")[1].count("\n"), 1)
        self.assertNotEqual(self.hook("PreCompact")[1], "")
        path = self.notes("Run R1: model strategy fixed\n" * 400)
        self.assertIn("cut here", self.hook("SessionStart")[1])
        self.assertIn("/notes/%s.md" % SESSION, self.hook("PreCompact")[1])
        os.remove(path)
        for name in ("grep", "sed"):
            os.rename(os.path.join(tools, name), os.path.join(tools, name + ".off"))
            for event in ("PreCompact", "SessionStart"):
                self.assert_silent(event)
            os.rename(os.path.join(tools, name + ".off"), os.path.join(tools, name))

    def test_nothing_is_written(self):
        self.mark()
        self.notes("Run R1: model strategy fixed\n")
        before = snapshot(self.tmp), sorted(os.listdir(HERE))
        for event in ("PreCompact", "SessionStart"):
            self.assertNotEqual(self.hook(event)[1], "")
            self.hook(event, session_id="no-run-here")
            self.hook(event, raw="not json")
            self.hook(event, agent_id="a1")
        self.assertEqual((snapshot(self.tmp), sorted(os.listdir(HERE))), before)
        self.assertEqual(os.listdir(self.repo), [".git"])

    def test_hook_entries(self):
        hooks = json.loads(read(os.path.join(HERE, "hooks.json")))["hooks"]
        compact = [e for e in hooks["SessionStart"] if e.get("matcher") == "compact"]
        self.assertEqual(len(compact), 1, "SessionStart: one entry, matcher exactly `compact`")
        self.assertEqual(len(hooks["PreCompact"]), 1)
        self.assertNotIn("matcher", hooks["PreCompact"][0], "manual and automatic compactions")
        for event, entries in (("SessionStart", compact), ("PreCompact", hooks["PreCompact"])):
            self.assertEqual(len(entries[0]["hooks"]), 1)
            entry = entries[0]["hooks"][0]
            self.assertEqual(entry["type"], "command")
            self.assertEqual(entry["command"],
                             'sh "${CLAUDE_PLUGIN_ROOT}/hooks/manager-run-compact.sh" ' + event)
            self.assertEqual(entry.get("onFailure"), "continue")
            self.assertLessEqual(entry["timeout"], 10)
        self.assertTrue(os.access(HOOK, os.X_OK))

    def test_the_skill_writes_the_marker_the_hook_tests(self):
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        self.assertIn("write the run id to this session's marker file, `%s`" % MARKER, skill)
        self.assertIn("outside every repository", skill)
        self.assertIn("can't be written → go on without it", skill)
        self.assertIn("Remove both (`rm -f`) with a final report that leaves no decision batch "
                      "open, or when the owner ends the run", skill)
        self.assertIn('"$HOME/.claude/manager-runs/active/$id"', read(HOOK))

    def test_the_skill_keeps_the_notes_in_the_file_the_hook_reads(self):
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        self.assertIn("Keep your working-notes lines in `%s`, written then (`mkdir -p`; a new run "
                      "starts it fresh, a compaction keeps it); edit only the line that changed, never print the block. Can't be "
                      "written → state each line once, when set or changed." % NOTES, skill)
        self.assertIn('notes="$HOME/.claude/manager-runs/notes/$id.md"\n', read(HOOK))
        # Its own folder, beside the markers': a notes file is never a run marker.
        self.assertNotEqual(os.path.dirname(NOTES), os.path.dirname(MARKER))
        self.assertIn("your working-notes lines (the notes file, as the hook prints it)", skill)

    def test_session_start_prints_the_notes_verbatim(self):
        self.mark()
        alone = self.hook("SessionStart")[1]
        text = ("Run R2026-01-01-0000: model strategy fixed (owner: \"aynı modelle devam\")\n"
                "Project rules: CLAUDE.md, AGENTS.md\n\n"
                "  P3: PR #12, base 0123abc, a \\n and a %s stay as they are\n"
                "D2 → A: \"şöyle olsun\"")  # the last line without its newline
        self.notes(text)
        code, out, err = self.hook("SessionStart")
        self.assertEqual((code, err), (0, ""))
        first, header, rest = out.split("\n", 2)
        self.assertEqual(first + "\n", alone)
        self.assertEqual(header, "manager-plugin: the run's working notes, verbatim from "
                                 "~/.claude/manager-runs/notes/%s.md (keep that file current; "
                                 "never print it):" % SESSION)
        self.assertEqual(rest, text + "\n")
        self.assertNotIn("cut here", out)
        self.notes("")
        self.assertEqual(self.hook("SessionStart")[1], alone + header + "\n")

    def test_session_start_caps_the_notes(self):
        self.mark()
        for row in ("x" * 99, "ş" * 99, "→" * 60):
            lines = ["%03d %s" % (n, row) for n in range(300)]
            self.notes("\n".join(lines) + "\n")
            code, out, err = self.hook("SessionStart")
            self.assertEqual((code, err), (0, ""))
            self.assertLess(len(out), 10000,
                            "Claude Code cuts a hook's output at 10,000 characters")
            kept = out.split("\n")[2:-2]
            self.assertGreater(len(kept), 10)
            self.assertEqual(kept, lines[:len(kept)], "whole lines, from the first")
            self.assertEqual(out.split("\n")[-2], "manager-plugin: the notes were cut here (8,000 "
                                                  "characters): read the rest from that file.")
        self.notes("y" * 9000 + "\n")  # a line longer than the cap: none of it, and the cut said
        out = self.hook("SessionStart")[1]
        self.assertEqual(out.count("\n"), 3)
        self.assertNotIn("yyy", out)
        self.assertIn("cut here", out)
        fits = "z" * 7999 + "\n"  # exactly the cap: not cut
        self.notes(fits)
        self.assertTrue(self.hook("SessionStart")[1].endswith("):\n" + fits))

    def test_pre_compact_with_a_notes_file_points_to_it(self):
        self.mark()
        fallback = self.hook("PreCompact")[1]
        self.notes("Run R1: model strategy fixed\n", "another-session")  # not this session's
        self.assertEqual(self.hook("PreCompact")[1], fallback)
        self.notes("Run R1: model strategy fixed\n")
        code, out, err = self.hook("PreCompact")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("\n"), 1)
        self.assertLess(len(out), 700, "short: the notes come back from the file")
        self.assertTrue(out.startswith("manager-plugin: a manager run is in progress"))
        self.assertIn("Its working-notes lines are in ~/.claude/manager-runs/notes/%s.md and "
                      "come back verbatim after the compaction: don't copy them into the summary"
                      % SESSION, out)
        self.assertNotIn("keep every working-notes line", out)
        self.assertNotIn("Run R1", out)
        self.assertTrue(out.endswith('"Before the next action, re-read the manager skill and every '
                                     'file in its references/ whose trigger applies; never work '
                                     'from a summary of a file."\n'), out)
        self.assertIn("keep every working-notes line of the run verbatim",
                      " ".join(fallback.split()))

    def test_a_notes_file_without_a_marker_is_silent(self):
        self.notes("Run R1: model strategy fixed\n")
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)
        os.makedirs(os.path.join(self.home, ".claude", "manager-runs", "active"))
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event)
            self.assert_silent(event, agent_id="a1")
        self.mark()
        for event in ("PreCompact", "SessionStart"):
            self.assert_silent(event, agent_id="a1", agent_type="manager-plugin:implementer")
        path = self.notes("x\n")
        os.remove(path)
        os.makedirs(path)  # a folder is no notes file: as without one
        self.assertEqual(self.hook("SessionStart")[1].count("\n"), 1)

    def test_the_marker_is_written_only_once(self):
        """Step 0 runs again after a compaction; a second write would move the marker's time,
        which bounds the orchestrator's usage line (`usage.py --since <marker>`)."""
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        form = "[ -e <file> ] || echo <id> > <file>"
        self.assertIn("`%s`, only once (`%s`; `mkdir -p` its folder;" % (MARKER, form), skill)
        tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, tmp)
        marker = os.path.join(tmp, "active", SESSION)
        os.makedirs(os.path.dirname(marker))
        write = form.replace("<file>", '"%s"' % marker)
        subprocess.run(["sh", "-c", write.replace("<id>", "R2026-01-01-0900")], check=True)
        self.assertEqual(read(marker), "R2026-01-01-0900\n")
        os.utime(marker, (1000, 1000))
        for run in ("R2026-01-01-0900", "R2026-01-02-1000"):  # step 0 again; a wrong id
            subprocess.run(["sh", "-c", write.replace("<id>", run)], check=True)
        self.assertEqual(read(marker), "R2026-01-01-0900\n")
        self.assertEqual(os.path.getmtime(marker), 1000)


class SizeCeilingTest(unittest.TestCase):
    """Claude Code re-attaches about the first 5,000 tokens (some 20,000 characters) of an invoked
    skill after a compaction, and every dispatch reads a brief. A phase that adds text may raise a
    ceiling by what it adds. Words are counted as `str.split()` does (`wc -w` in a UTF-8 locale)."""

    def test_manager_skill_fits_the_reattach_budget(self):
        self.assertLessEqual(len(read(os.path.join(MANAGER, "SKILL.md"))), 17600)

    def test_code_map_skill(self):
        """9,108 characters at 0.9.10, after its rare paths moved to `references/`; 9,347 at
        0.9.11."""
        self.assertLessEqual(len(read(os.path.join(SKILLS, "code-map", "SKILL.md"))), 9500)

    def test_rare_path_pointers_resolve(self):
        """A rare-path block moved out of a SKILL.md leaves a pointer: every `references/<file>`
        the skill names exists, and every file in its `references/` is named there."""
        for skill in ("code-map", "self-training-skills"):
            folder = os.path.join(SKILLS, skill)
            text = " ".join(read(os.path.join(folder, "SKILL.md")).split())
            named = set(re.findall(r"`references/([a-z0-9-]+\.md)`", text))
            here = set(os.listdir(os.path.join(folder, "references")))
            self.assertEqual(named, here, skill)

    def test_briefs(self):
        for name, words in (("implementer-brief.md", 1327), ("reviewer-brief.md", 1347)):
            self.assertLessEqual(len(read(os.path.join(REFS, name)).split()), words, name)


class ReferencePointerTest(unittest.TestCase):
    """Step detail lives in `references/`, each file read at a trigger the skill names; a rule that
    moved out of the skill exists exactly once."""

    def setUp(self):
        self.texts = manager_texts()
        self.skill = self.texts["SKILL.md"]

    def test_every_reference_is_named_and_every_named_one_exists(self):
        named = set(re.findall(r"`references/([a-z0-9-]+\.md)`", self.skill))
        self.assertIn("`${CLAUDE_SKILL_DIR}/references/implementer-brief.md` and "
                      "`reviewer-brief.md`", self.skill)
        named.update(("implementer-brief.md", "reviewer-brief.md"))
        briefs = self.texts["implementer-brief.md"] + self.texts["reviewer-brief.md"]
        for name in self.texts:
            if name == "SKILL.md":
                continue
            if name.startswith("brief-"):
                self.assertIn("`%s`" % name, briefs, name)
            else:
                self.assertIn(name, named, "%s: no pointer from the skill" % name)
        for name in named:
            self.assertIn(name, self.texts, "%s: named by the skill, missing" % name)

    def test_references_state_their_trigger(self):
        for name in ("approach-check.md", "code-map-check.md", "dispatch.md", "establish-state.md",
                     "final-report.md", "landing.md", "model-strategy.md", "no-report.md",
                     "plan-only-pr.md", "recurring-blocker.md", "review-round.md",
                     "run-record.md", "self-training-due.md", "session-check.md",
                     "verify-candidate.md"):
            self.assertRegex(self.texts[name], r"^# [^#]+? Read by the manager skill ", name)

    def test_section_names_the_references_cite_resolve_in_the_skill(self):
        for name in ("Rotation", "Series mode", "Ignored-data guard", "Integration method",
                     "Which strategy applies", "Asking", "Applying", "Not enough model",
                     "Plan records", "Plan-only PR", "Brakes", "Stop conditions",
                     "Sequential phases", "Phases and scheduling", "Owner decisions",
                     "Run record", "Code map", "Run marker"):
            self.assertRegex(self.skill, r"(\*\*%s\b|## %s\b)" % (name, name), name)

    def test_moved_rules_exist_exactly_once(self):
        for rule, home in (
                ("ls-files --others --ignored --exclude-standard --directory", "dispatch.md"),
                ("A drop the dispatch can't explain", "dispatch.md"),
                ("Never use `manager-plugin:worker` for a phase", "dispatch.md"),
                ("only if the project rules don't forbid force-pushing", "dispatch.md"),
                ("never one verdict for several PRs", "dispatch.md"),
                ("about 150k or more", "dispatch.md"),
                ("a recorded `run` strategy is never applied by inference", "model-strategy.md"),
                ("never fall back to a standing policy for a run already under way",
                 "model-strategy.md"),
                ("Model tercihiniz hangisi?", "model-strategy.md"),
                ("don't escalate", "model-strategy.md"),
                ("an incomplete plugin copy", "establish-state.md"),
                ("a ledger PASS is never a reason to skip it", "establish-state.md"),
                ("the files they import with `@path`", "establish-state.md"),
                ("on MCP the PR read is its own call", "verify-candidate.md"),
                ("never the living plan or the project rules files", "verify-candidate.md"),
                ("never discard anyone's changes", "review-round.md"),
                ("Never restore or remove anything on a tree that was dirty before the review",
                 "review-round.md"),
                ("resume the **same** reviewer", "review-round.md"),
                ("`<k>` counts every ledger line", "review-round.md"),
                ("never a fix round of their own", "review-round.md"),
                ("never abandon a sound approach over them", "approach-check.md"),
                ("a design change is an owner decision", "approach-check.md"),
                ("the default branch's final head SHA", "final-report.md"),
                ("`git switch --detach origin/<default>`", "final-report.md"),
                ("blocks any plan record in the diff that doesn't match it",
                 "owner-decisions.md"),
                ("land one plan-only bookkeeping PR", "owner-decisions.md"),
                ("green validation alone is not acceptance", "plan-only-pr.md"),
                ("the rules and the merge call's own refusal", "landing.md"),
                ("never for the hooks line alone", "code-map-check.md")):
            found = {name: text.count(rule) for name, text in self.texts.items() if rule in text}
            self.assertEqual(found, {home: 1}, rule)
        # Moved out of a SKILL.md in 0.9.10: one key sentence each, counted in every skill's
        # SKILL.md and references.
        paths = sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))
                       + glob.glob(os.path.join(SKILLS, "*", "references", "*.md")))
        texts = {os.path.relpath(p, SKILLS).replace(os.sep, "/"): " ".join(read(p).split())
                 for p in paths}
        for rule, home in (
                ("the deepest folder holding at least 80% of the pages with `[[wikilinks]]`",
                 "code-map/references/layout.md"),
                ("Install only after the owner agrees in this conversation",
                 "code-map/references/python-install.md"),
                ("`--remove` deletes only such a file, and only when nothing but its title is left",
                 "code-map/references/setup.md"),
                ("An existing `pre-commit` hook is kept as `pre-commit.codemap-chained` and runs "
                 "first", "code-map/references/commit-hooks.md"),
                ("Each subagent counts on its own", "code-map/references/search-nudge.md"),
                ("No living plan \u2192 the run can't start", "manager/references/no-plan.md"),
                ("stops that landing only", "manager/references/refused-landing.md"),
                ("an unmarked one is never checked or trained by this skill",
                 "self-training-skills/references/adopt.md")):
            found = {name: text.count(rule) for name, text in texts.items() if rule in text}
            self.assertEqual(found, {home: 1}, rule)

    def test_the_final_report_step_reaches_the_bookkeeping_pr(self):
        """The skill sends the final-report step to `final-report.md` alone; the end-of-run
        bookkeeping PR's rule is in `owner-decisions.md`."""
        self.assertIn("still unpersisted (an owner's answer, a status correction) → first "
                      "`references/owner-decisions.md`, **Plan records**: the end-of-run "
                      "bookkeeping PR.", self.texts["final-report.md"])

    def test_idle_compaction_is_recommended_and_the_compact_line_stays(self):
        """Idle compaction covers only a local session whose context has reached its threshold:
        the session check recommends the lowest threshold, and the line at a stop stays."""
        check = self.texts["session-check.md"]
        for words in ("(d) Idle compaction, in a local session only",
                      "recommend `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS=100000`",
                      "the delay is not a setting",
                      "It doesn't replace the final report's `/compact` line"):
            self.assertIn(words, check, words)
        self.assertIn("answering after more than about 50 minutes → run `/compact` now, or answer "
                      "in a new session", self.texts["final-report.md"])

    def test_what_a_compaction_re_reads(self):
        """A reference whose rules the later steps still need says "again after a compaction", in
        the skill's pointer and in its own first lines; the in-flight phase's section is re-read
        too, and read first by a phase that resumes at step 2 (step 1 never read it)."""
        for name in ("dispatch.md", "establish-state.md", "model-strategy.md"):
            pointer = re.search(r"[^.]* read `references/%s`" % re.escape(name), self.skill)
            self.assertIsNotNone(pointer, name)
            own = re.search(r"Read by the manager skill [^.:]*", self.texts[name]).group(0)
            for trigger in (pointer.group(0), own):
                self.assertIn("again after a compaction", trigger, name)
                self.assertNotIn("compaction that", trigger, name)
        self.assertRegex(self.skill, r"After a compaction, before acting, re-read [^.;]*the "
                                     r"in-flight phase's section as on its base SHA \(loop "
                                     r"step 1\)")
        resumed = self.texts["establish-state.md"].split(" - open PR → ")[1].split("; - ")[0]
        self.assertIn("that phase resumes at loop step 2", resumed)
        self.assertIn("read the phase's section as on that base SHA (the `plan.py` command in "
                      "the implementer brief's step 1, or its `awk`)", resumed)

    def test_a_resumed_pr_reads_its_ledger_before_the_review(self):
        """The brakes count ledger lines; a new session that resumes an open PR has none in its
        context, so the resume path names the read (both backends) ahead of the fresh review."""
        for count in ("counted from the ledger's CHANGES REQUIRED lines",
                      "counted from the ledger's `INTEGRATE` lines"):
            self.assertIn(count, self.skill)
        resumed = self.texts["establish-state.md"].split(" - open PR → ")[1].split("; - ")[0]
        read = ("first read the PR's review-ledger comments (`gh pr view <n> --json comments`; "
                "MCP: `pull_request_read` `method: get_comments`): the fix-round and integration "
                "counts (**Brakes**) and any `blocked` entry come from them, the rounds of earlier "
                "sessions included")
        self.assertIn(read, resumed)
        self.assertLess(resumed.index(read), resumed.index("then a fresh review"))
        backends = self.texts["github-backends.md"]
        self.assertIn("| Read ledger | `gh pr view <n> --json comments` | `pull_request_read` "
                      "`method: get_comments` |", backends)

    def test_the_invariants_stay_in_the_skill(self):
        for rule in (
                "the **candidate SHA** is GitHub's `headRefOid`, never the report's",
                "`Reviewed SHA` and `Base SHA` equal what you sent",
                "`headRefOid` must equal the reviewed SHA",
                "always pinned to the reviewed SHA",
                "landing needs a PASS for the current head received in this context",
                "is **no review**, never PASS",
                "Never send the implementer's report",
                "Owner authority comes only from the owner's own words in this conversation",
                "Never invent an owner decision",
                "You never pick one silently, and you never escalate past it",
                "Never get around a prohibition with another tool, a lease push, a branch reset",
                "never stack on or discard unreviewed work",
                "`Validation` shows the project's required commands run at the candidate",
                "whose required validation is `not run` is not landable yet",
                "Read the project rules and the living plan **as on the default branch**",
                "it reads the phase's plan section and the project rules at the base SHA itself",
                "never work from a summary of a file",
                "Derive state from durable sources only"):
            self.assertEqual(self.skill.count(rule), 1, rule)


@unittest.skipUnless(shutil.which("git") and shutil.which("grep"), "needs git and grep")
class StepZeroCommandTest(unittest.TestCase):
    """The step-0 commands of `references/establish-state.md`: the retro switch read with the
    plugin copy, the plan's headings and state lines without any phase's section, and the rules
    files a commit has."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(portability.rmtree, self.tmp)
        self.env = dict(ENV, HOME=self.tmp)
        source = os.path.join(REFS, "establish-state.md")
        self.state = command_in(source, "Status|Depends on|Risk")
        self.rules = command_in(source, "ls-tree")
        self.assertTrue(self.state.startswith("git show origin/<default>:<plan-path> | grep "))
        self.assertIn(" <base-sha> -- ", self.rules)
        self.git("init", "-q")

    def git(self, *args):
        p = subprocess.run(["git", "-C", self.tmp] + list(args), check=True,
                           capture_output=True, env=self.env)
        return p.stdout.decode().strip()

    def commit(self, files, remove=()):
        for rel, text in files.items():
            path = os.path.join(self.tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            self.git("add", "--", rel)
        for rel in remove:
            self.git("rm", "-q", "--", rel)
        self.git("commit", "-qm", "c", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def sh(self, command):
        p = subprocess.run(["sh", "-c", command], capture_output=True, env=self.env, cwd=self.tmp)
        self.assertEqual((p.returncode, p.stderr.decode()), (0, ""), command)
        return p.stdout.decode("utf-8")

    def test_item_1_reads_the_retro_switch_the_version_and_the_plugin_copy(self):
        """One Bash call, as the orchestrator runs it with the skill's folder filled in: the
        switch's line first, then the plugin's version line and the reference files; it writes
        nothing, in the home folder or in the repository."""
        command = command_in(os.path.join(REFS, "establish-state.md"), "retro.sh")
        self.assertEqual(command.split("\n"), [
            'sh "${CLAUDE_SKILL_DIR}/scripts/retro.sh"',
            'grep \'"version"\' "${CLAUDE_SKILL_DIR}/../../.claude-plugin/plugin.json"',
            'ls "${CLAUDE_SKILL_DIR}/references"'])
        command = command.replace("${CLAUDE_SKILL_DIR}", os.path.abspath(MANAGER))
        with open(os.path.join(MANAGER, "..", "..", ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as fh:
            version = json.load(fh)["version"]
        flag = os.path.join(self.tmp, ".claude", "manager-plugin", "retro")
        os.makedirs(os.path.dirname(flag))
        for name in ("MANAGER_RETRO", "CLAUDE_CONFIG_DIR"):
            self.env.pop(name, None)
        for switch, setting in (("off (no flag file)", None), ("on (flag file)", flag),
                                ("off (MANAGER_RETRO)", "off"), ("on (MANAGER_RETRO)", "on")):
            if setting == flag:
                with open(flag, "w", encoding="utf-8"):
                    pass
            elif setting:
                self.env["MANAGER_RETRO"] = setting
            before = snapshot(self.tmp)
            lines = self.sh(command).splitlines()
            with self.subTest(switch=switch):
                self.assertEqual(lines[0], switch)
                self.assertEqual(json.loads("{%s}" % lines[1].strip().rstrip(",")),
                                 {"version": version})
                self.assertEqual(sorted(lines[2:]), sorted(os.listdir(REFS)))
                self.assertLessEqual({"implementer-brief.md", "reviewer-brief.md",
                                      "github-backends.md", "establish-state.md"}, set(lines[2:]))
                self.assertEqual(len([name for name in lines[2:]
                                      if name.startswith("brief-")]), 6)
                self.assertEqual(snapshot(self.tmp), before)

    def plan_state(self, plan):
        sha = self.commit({"docs/LIVING PLAN.md": plan})
        out = self.sh(self.state.replace("origin/<default>:<plan-path>",
                                         '%s:"docs/LIVING PLAN.md"' % sha))
        lines = plan.split("\n")
        found = []
        for row in out.splitlines():
            number, text = row.split(":", 1)
            self.assertEqual(lines[int(number) - 1], text)
            found.append(text)
        return found

    def test_plan_state_of_the_template_shape(self):
        template = command_in(os.path.join(SKILLS, "living-plan", "references",
                                           "plan-template.md"), "## Binding decisions")
        self.assertIn("### P2. <title>\n...\n", template)
        plan = template.replace(
            "### P2. <title>\n...\n",
            "### P2. Second\nStatus: blocked (D1)\nObjective: the second thing\n"
            "Depends on: P1\nRisk: critical — numbers\nAcceptance: Status: shown\n")
        found = self.plan_state(plan)
        for kept in ("## Binding decisions", "## Phases", "### P1. <title>", "Status: todo",
                     "### P2. Second", "Status: blocked (D1)", "Depends on: P1",
                     "Risk: critical — numbers", "## Open owner decisions", "### D1. <question>"):
            self.assertIn(kept, found)
        self.assertEqual([t for t in found if not t.startswith("#")],
                         [t for t in plan.split("\n")
                          if t.startswith(("Status: ", "Depends on: ", "Risk: "))])
        for text in found:  # no line of a phase's section but its three state lines
            self.assertRegex(text, r"^(#|Status: |Depends on: |Risk: )")
        self.assertLess(len(" ".join(found).split()), len(plan.split()) * 0.3)

    def test_the_skill_reads_a_phase_section_only_when_the_phase_is_scheduled(self):
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        self.assertIn("of the plan, no phase's section before that phase is scheduled", skill)
        self.assertIn("Read the phase's section as on it (the implementer brief's step 1: "
                      "`plan.py`)", skill)
        self.assertNotIn("the remaining phases' sections", " ".join(manager_texts().values()))

    def rules_files(self, sha):
        return self.sh(self.rules.replace("<base-sha>", sha)).splitlines()

    def test_rules_files_are_listed_as_on_each_base(self):
        first = self.commit({"README.md": "x\n", "src/CLAUDE.md": "not a rules file here\n"})
        self.assertEqual(self.rules_files(first), [])  # the `Project rules` field: none
        second = self.commit({"CLAUDE.md": "@AGENTS.md\n", "AGENTS.md": "rules\n"})
        self.assertEqual(self.rules_files(second), ["AGENTS.md", "CLAUDE.md"])
        third = self.commit({".claude/rules/api style.md": "r\n", ".claude/CLAUDE.md": "r\n"},
                            remove=["AGENTS.md"])
        self.assertEqual(sorted(self.rules_files(third)),
                         [".claude/CLAUDE.md", ".claude/rules/api style.md", "CLAUDE.md"])
        self.assertEqual(self.rules_files(second), ["AGENTS.md", "CLAUDE.md"])
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        self.assertIn("when the default head has moved since the `Project rules` line was taken, "
                      "list the rules files again as on it (`references/establish-state.md`",
                      skill)


if __name__ == "__main__":
    unittest.main()
