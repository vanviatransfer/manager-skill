# Adopt mode

Read by the self-training-skills skill in Adopt mode (an existing skill made without this plugin).
Bold mode names, step numbers and `<cmd>` are that skill's.

**Adopt.** For an existing skill made without this plugin, keep its structure and files and leave
it as it is. `check` applies only to marked skills, so an unmarked one is never checked or trained
by this skill. Adding the marker means bringing the skill into the template's shape too: the six
sections in order, a citation on every rule, a `Records:` line, `lessons.md` and the changelog. Do
that only with the owner's agreement; otherwise it stays unmarked. A project tool that already
checks or maps its skills (as in Create, step 1) is used, not duplicated; replacing it is an owner
decision. After marking, run `<cmd> check <skill dir> --triggers-from <base ref>` (the branch's
base, e.g. `origin/<default>`; mandatory here: it holds the description's trigger phrases, the
skill's own and a retired trainer's) and `<cmd> rules-hint <repo root>`.
