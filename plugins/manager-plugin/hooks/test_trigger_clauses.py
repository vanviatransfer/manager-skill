"""Every model-invoked skill's description keeps a "Use when" / "Use for" trigger clause and every
agent's description its "Use ..." clause: Claude Code picks a skill or an agent from its
description alone. python3 -m unittest discover -s <this folder>"""
import os
import re
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")


def frontmatter(path):
    """{key: value} of a markdown file's leading `---` block, one `key: value` line each."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    assert lines[0].strip() == "---", path
    found = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return found
        match = re.match(r"([A-Za-z-]+):\s*(.*)$", line)
        if match:
            found[match.group(1)] = match.group(2).strip().strip("\"'")
    raise AssertionError("%s: the frontmatter is not closed" % path)


class TriggerClauseTest(unittest.TestCase):

    def test_model_invoked_skills(self):
        checked = []
        for name in sorted(os.listdir(SKILLS)):
            path = os.path.join(SKILLS, name, "SKILL.md")
            if not os.path.isfile(path):
                continue
            meta = frontmatter(path)
            if meta.get("disable-model-invocation", "").lower() == "true":
                continue  # invoked by the owner only: no trigger needed
            self.assertRegex(meta.get("description", ""), r"\bUse (?:when|for)\b", name)
            checked.append(name)
        self.assertGreaterEqual(len(checked), 5, checked)

    def test_agents(self):
        names = sorted(name for name in os.listdir(AGENTS) if name.endswith(".md"))
        self.assertGreaterEqual(len(names), 5, names)
        for name in names:
            description = frontmatter(os.path.join(AGENTS, name)).get("description", "")
            self.assertRegex(description, r"\bUsed? (?:only when|instead of|when|for)\b", name)


if __name__ == "__main__":
    unittest.main()
