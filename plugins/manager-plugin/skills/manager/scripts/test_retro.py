"""Tests for retro.sh, the retro switch (whether manager runs keep a run record), in a temporary
home, and for the texts that send the manager and the manager-retro skill to it:
python3 -m unittest discover -s <this folder>"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
SCRIPT = os.path.join(HERE, "retro.sh")
MANAGER = os.path.dirname(HERE)
RETRO_SKILL = os.path.join(os.path.dirname(MANAGER), "manager-retro", "SKILL.md")
ON, OFF = "on (flag file)\n", "off (no flag file)\n"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def tree(top):
    """{relative path: content, or None for a folder} of everything under `top`."""
    found = {}
    for folder, _, files in os.walk(top):
        found[os.path.relpath(folder, top)] = None
        for name in files:
            path = os.path.join(folder, name)
            found[os.path.relpath(path, top)] = read(path)
    return found


class RetroSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = os.path.join(self.tmp, "my home")
        self.cwd = os.path.join(self.tmp, "repo")
        os.makedirs(self.home)
        os.makedirs(os.path.join(self.cwd, ".git"))
        self.flag = os.path.join(self.home, ".claude", "manager-plugin", "retro")

    def run_script(self, *args, **env):
        """(exit status, stdout, stderr) of retro.sh with only PATH, HOME and `env` set (None
        drops a variable), started in a repository."""
        full = {"PATH": os.environ.get("PATH", ""), "HOME": self.home}
        full.update(env)
        full = {key: value for key, value in full.items() if value is not None}
        p = subprocess.run(["sh", SCRIPT] + list(args), capture_output=True, env=full,
                           cwd=self.cwd, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")

    def touch(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8"):
            pass

    def test_the_default_is_off_and_asking_writes_nothing(self):
        for args in ((), ("status",), ("",)):
            self.assertEqual(self.run_script(*args), (0, OFF, ""), args)
        self.assertEqual(tree(self.tmp), {".": None, "my home": None, "repo": None,
                                          os.path.join("repo", ".git"): None})

    def test_the_flag_file_turns_it_on(self):
        self.touch(self.flag)
        for args in ((), ("status",)):
            self.assertEqual(self.run_script(*args), (0, ON, ""), args)
        self.assertTrue(os.path.exists(self.flag))

    def test_the_config_folder_is_claude_config_dir_when_set(self):
        """As usage.py resolves it: `CLAUDE_CONFIG_DIR`, else `~/.claude`; an empty value is
        not set."""
        other = os.path.join(self.tmp, "config folder")
        self.touch(self.flag)
        self.assertEqual(self.run_script(CLAUDE_CONFIG_DIR=other), (0, OFF, ""))
        self.assertEqual(self.run_script(CLAUDE_CONFIG_DIR=""), (0, ON, ""))
        os.remove(self.flag)
        self.touch(os.path.join(other, "manager-plugin", "retro"))
        self.assertEqual(self.run_script(CLAUDE_CONFIG_DIR=other), (0, ON, ""))
        self.assertEqual(self.run_script(), (0, OFF, ""))

    def test_the_environment_variable_overrides_the_file(self):
        for value in ("on", "ON", "On"):
            self.assertEqual(self.run_script(MANAGER_RETRO=value), (0, "on (MANAGER_RETRO)\n", ""))
        self.touch(self.flag)
        for value in ("off", "OFF", "Off"):
            self.assertEqual(self.run_script(MANAGER_RETRO=value),
                             (0, "off (MANAGER_RETRO)\n", ""))
        self.assertTrue(os.path.exists(self.flag))

    def test_another_value_of_the_variable_is_ignored(self):
        for value in ("", "1", "0", "true", "yes", "no", "onn", " on", "on off"):
            self.assertEqual(self.run_script(MANAGER_RETRO=value), (0, OFF, ""), value)
        self.touch(self.flag)
        for value in ("", "1", "0", "false", "no", "of"):
            self.assertEqual(self.run_script(MANAGER_RETRO=value), (0, ON, ""), value)

    def test_on_and_off_write_and_remove_that_one_file(self):
        self.assertEqual(self.run_script("on"), (0, ON, ""))
        self.assertTrue(os.path.isfile(self.flag))
        self.assertEqual(self.run_script("on"), (0, ON, ""))  # already on
        self.assertEqual(self.run_script("off"), (0, OFF, ""))
        self.assertFalse(os.path.exists(self.flag))
        self.assertEqual(self.run_script("off"), (0, OFF, ""))  # already off
        self.assertEqual(tree(self.cwd), {".": None, ".git": None})
        other = os.path.join(self.tmp, "config folder")
        self.assertEqual(self.run_script("on", CLAUDE_CONFIG_DIR=other), (0, ON, ""))
        self.assertTrue(os.path.isfile(os.path.join(other, "manager-plugin", "retro")))
        self.assertFalse(os.path.exists(self.flag))

    def test_on_and_off_say_when_the_variable_decides(self):
        self.assertEqual(self.run_script("on", MANAGER_RETRO="off"),
                         (0, "off (MANAGER_RETRO)\n", ""))
        self.assertTrue(os.path.isfile(self.flag))
        self.assertEqual(self.run_script("off", MANAGER_RETRO="on"),
                         (0, "on (MANAGER_RETRO)\n", ""))
        self.assertFalse(os.path.exists(self.flag))

    def test_run_records_are_never_touched(self):
        runs = os.path.join(self.home, ".claude", "manager-runs")
        for name, text in (("2026-01-01-repo-R2026-01-01-0900.md", "# repo R · plugin 0.9.1\n"),
                           ("retro-log.md", "2026-01-02 0.9.1\n"),
                           (os.path.join("active", "0f3c9a1e"), "R2026-01-01-0900\n")):
            path = os.path.join(runs, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        before = tree(runs)
        for args in (("on",), ("status",), ("off",), ("off",), ()):
            self.assertEqual(self.run_script(*args)[0], 0, args)
            self.assertEqual(tree(runs), before, args)

    def test_a_file_that_cannot_be_written_is_reported(self):
        blocked = os.path.join(self.tmp, "a file")
        self.touch(blocked)  # the config folder's path is a file: nothing can be made below it
        code, out, err = self.run_script("on", CLAUDE_CONFIG_DIR=blocked)
        self.assertEqual((code, out), (1, OFF))
        self.assertIn("cannot write", err)
        code, out, err = self.run_script("on", HOME=None)
        self.assertEqual((code, out), (1, OFF))
        self.assertIn("no CLAUDE_CONFIG_DIR and no HOME", err)
        self.assertEqual(self.run_script(HOME=None), (0, OFF, ""))
        self.assertEqual(self.run_script("off", HOME=None), (0, OFF, ""))

    def test_another_argument_changes_nothing(self):
        self.touch(self.flag)
        before = tree(self.tmp)
        for args in (("toggle",), ("ON",), ("on", "off"), ("status", "x"), ("", "on")):
            code, out, err = self.run_script(*args)
            self.assertEqual((code, out), (2, ""), args)
            self.assertIn("usage: retro.sh [status|on|off]", err)
            self.assertEqual(tree(self.tmp), before, args)


class RetroTextTest(unittest.TestCase):
    """The manager checks the switch at step 0 and keeps no run record while it is off; the
    manager-retro skill turns it on and off and costs other sessions nothing."""

    def test_the_manager_skill_checks_the_switch_before_any_run_record(self):
        skill = " ".join(read(os.path.join(MANAGER, "SKILL.md")).split())
        section = skill[skill.index("## Run record"):skill.index("## Stop conditions")]
        self.assertIn('`sh "${CLAUDE_SKILL_DIR}/scripts/retro.sh"`', section)
        self.assertIn("step 0", section)
        self.assertRegex(section, r"prints `on …` → [^.]*read `references/run-record\.md` "
                                  r"before its first write")
        self.assertIn("no record and no `usage.py`", section)

    def test_the_run_record_reference_states_the_rule(self):
        text = " ".join(read(os.path.join(MANAGER, "references", "run-record.md")).split())
        head = text[:text.index("So that runs can be compared")]
        for words in ("only while the retro switch is on",
                      "The default is off",
                      '`sh "${CLAUDE_SKILL_DIR}/scripts/retro.sh"`',
                      "`MANAGER_RETRO=on` or `off`",
                      "write no run record and run no `usage.py`",
                      "Never turn the switch on or off yourself",
                      "never delete or change a record"):
            self.assertIn(words, head, words)

    def test_the_final_report_is_silent_about_a_record_while_off(self):
        text = " ".join(read(os.path.join(MANAGER, "references", "final-report.md")).split())
        self.assertIn("the run record path, or why it was skipped (retro switch off: neither)",
                      text)

    def test_the_retro_skill_is_typed_only_and_names_the_script(self):
        text = read(RETRO_SKILL)
        front = text.split("---\n")[1]
        self.assertIn("disable-model-invocation: true\n", front)
        description = re.search(r'^description: "?(.*?)"?$', front, re.M).group(1)
        self.assertLessEqual(len(description), 100)
        body = " ".join(text.split("---\n", 2)[2].split())
        command = '`sh "${CLAUDE_SKILL_DIR}/../manager/scripts/retro.sh" <status|on|off>`'
        self.assertIn(command, body)
        self.assertEqual(os.path.normpath(os.path.join(os.path.dirname(RETRO_SKILL), "..",
                                                       "manager", "scripts", "retro.sh")), SCRIPT)
        self.assertIn("$ARGUMENTS", body)
        for words in ("`/manager-plugin:manager-retro on`", "`MANAGER_RETRO=on`",
                      "never delete a run record"):
            self.assertIn(words, body, words)

    def test_the_retro_goes_on_with_records_written_before_the_switch_went_off(self):
        """Off stops new records, not the retro: it says so, then measures what was recorded
        while the switch was on, and stops only when there is no dated record."""
        body = " ".join(read(RETRO_SKILL).split())
        rule = body[body.index("- Anything else, or no arguments"):
                    body.index("- The switch never deletes a run record")]
        self.assertIn("run it with `status`. `on` → continue below. `off` → say that recording "
                      "is off, so manager runs record nothing", rule)
        self.assertIn("none → stop; one or more → say how many there are and continue below "
                      "with those records.", rule)
        self.assertNotIn("then stop", rule)
        listing = re.search(r"\(`(ls ~/\.claude/manager-runs/\S+)` through Bash\)", rule).group(1)
        self.assertIn("`cat %s`" % listing[len("ls "):], body)  # the files step 1 reads
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        runs = os.path.join(home, ".claude", "manager-runs")
        os.makedirs(os.path.join(runs, "active"))

        def dated():
            p = subprocess.run(["sh", "-c", listing], capture_output=True, cwd=home,
                               env={"PATH": os.environ.get("PATH", ""), "HOME": home})
            return p.returncode == 0, [os.path.basename(line)
                                       for line in p.stdout.decode("utf-8").splitlines()]
        for name in ("retro-log.md", os.path.join("active", "0f3c9a1e")):
            with open(os.path.join(runs, name), "w", encoding="utf-8"):
                pass
        self.assertEqual(dated(), (False, []))  # the retro log and a run marker are no record
        names = ["2026-01-01-repo-R2026-01-01-0900.md", "2026-01-03-repo-R2026-01-03-1000.md"]
        for name in names:
            with open(os.path.join(runs, name), "w", encoding="utf-8"):
                pass
        self.assertEqual(dated(), (True, names))


if __name__ == "__main__":
    unittest.main()
