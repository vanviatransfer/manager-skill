"""Tests for prefer-plugin-agents.sh: python3 -m unittest discover -s <this folder>"""
import json
import os
import subprocess
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefer-plugin-agents.sh")


def run(payload):
    data = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run(["sh", HOOK], input=data.encode(), capture_output=True)
    return p.returncode, p.stderr.decode()


def spawn(**tool_input):
    return {"tool_name": "Agent", "tool_input": tool_input}


class HookTest(unittest.TestCase):
    def test_general_purpose_is_blocked_with_guidance(self):
        code, err = run(spawn(subagent_type="general-purpose", prompt="fix the bug"))
        self.assertEqual(code, 2)
        for agent in ("worker", "researcher", "reviewer"):
            self.assertIn("manager-plugin:" + agent, err)
        self.assertNotIn("implementer", err)

    def test_missing_type_defaults_to_general_purpose(self):
        self.assertEqual(run(spawn(prompt="x", description="d"))[0], 2)

    def test_other_agents_pass(self):
        for t in ("manager-plugin:worker", "manager-plugin:implementer", "Explore", "Plan"):
            self.assertEqual(run(spawn(subagent_type=t, prompt="x"))[0], 0, t)

    def test_escape_hatch(self):
        p = spawn(subagent_type="general-purpose", prompt="[general-purpose: needs Gmail] x")
        self.assertEqual(run(p)[0], 0)

    def test_quoted_text_in_prompt_is_not_the_field(self):
        p = spawn(subagent_type="Explore", prompt='say "subagent_type": "general-purpose"')
        self.assertEqual(run(p)[0], 0)

    def test_pretty_printed_input(self):
        data = json.dumps(spawn(subagent_type="general-purpose", prompt="x"), indent=2)
        self.assertEqual(run(data)[0], 2)

    def test_null_type_and_name_variants_are_blocked(self):
        self.assertEqual(run(spawn(subagent_type=None, prompt="x"))[0], 2)
        for t in ("General-Purpose", "general_purpose", "GeneralPurpose"):
            self.assertEqual(run(spawn(subagent_type=t, prompt="x"))[0], 2, t)

    def test_hook_entry_fails_open_on_windows_without_bash(self):
        with open(os.path.join(os.path.dirname(HOOK), "hooks.json")) as fh:
            entry = json.load(fh)["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(entry.get("onFailure"), "continue")

    def test_unexpected_input_fails_open(self):
        self.assertEqual(run("not json")[0], 0)
        self.assertEqual(run("")[0], 0)


if __name__ == "__main__":
    unittest.main()
