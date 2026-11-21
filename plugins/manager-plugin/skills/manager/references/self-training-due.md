# Self-training skills due

Read by the manager skill when it writes the final report.

When the default branch has marked skills under `.claude/skills/` (`grep -l
"<!-- self-training-skill v1 -->" .claude/skills/*/SKILL.md`), run `<python>
"${CLAUDE_SKILL_DIR}/../self-training-skills/scripts/skilltrain.py" due <repo root>` (the Python
as the code-map skill's rule picks it) and list, before the decision batch, each skill due for
training with `"<skill> için eğitim zamanı: 'skill'i eğit <skill>' deyin"`. Without Python, skip
this and say so in the report.
Run the grep and `due` only when the shared checkout's `HEAD` equals `origin/<default>` (the
end-of-run switch in **Stop conditions** makes it so where it is allowed), so they
read the default branch's state; otherwise skip them and say so. Say also that phase rows stay
`pending-review` until a training resolves them, so for those only the 5-records trigger applies.
Marked worker skills are not listed in the step-0 line's "disable for this repo if unneeded".
