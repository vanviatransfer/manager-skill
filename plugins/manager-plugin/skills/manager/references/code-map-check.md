# Code map check

Read by the manager skill at step 6 of every run (**Code map**), and again after a compaction while
the check or a setup PR is still open. It covers the vault, the code map and the rules block
(the `code-map` skill's **The rules block**); they are set up together, in one setup PR.

- **Set up** = on the default branch: a vault (`.codemap.json`'s `vault`), `.codemap.json` with a
  `map` (`git show origin/<default>:.codemap.json`), and the rules block (`git show
  origin/<default>:AGENTS.md` holds `manager-plugin:code-map:begin`; `CLAUDE.md` holds it or the
  `manager-plugin:code-map:` import line). Those committed files are the guard: once they land,
  later runs only resolve the command and never ask again. Resolve it as the `code-map` skill says
  (script `${CLAUDE_SKILL_DIR}/../code-map/scripts/codemap.py`, a Python 3.8+) and send `Code map:
  <cmd>` in every dispatch. No Python: offer the install (the gate's Python line, or its own
  question when the gate isn't asked); declined → `Code map: none` this run, and say in the final
  report that the map stays stale until a run with Python rebuilds it.
- **Not a plain file** (`git ls-tree origin/<default> .codemap.json` shows mode `120000`, a
  symlink; check this first): don't ask; use `Code map: none` and report it, so the owner can
  replace it with a plain file.
- **Declined:** a valid Decided entry in the plan on the default branch, or a project rule, that
  declines the vault or the map is honoured: set up only what it leaves, never ask about the rest.
- **No vault** (none on the default branch and no `vault` in `.codemap.json`): ask the gate's vault
  question, with the Python line if Python is missing and the hooks line.
  - **Evet:** the setup PR below, with a new vault (`create-vault`'s Create mode).
  - **Bu sefer hayır:** nothing is set up this run (an existing map still gets its `Code map`
    command); asked again next run.
  - **Bir daha sorma:** record it as a Decided owner decision (owner's words, date) through the
    next landing PR's `Plan records`, or the end-of-run plan-only PR. A valid one stops the
    question in later runs; the owner can still ask for a vault with the `create-vault` skill.
- **A vault, but no map or no rules block:** the setup PR below without asking; only the hooks
  line (and the Python line if Python is missing) goes into the gate. Python declined → the PR
  holds the rules block only; report that the map isn't set up.
- **Hooks line** (only when a setup PR is to be made): yes → dispatch `Setup: code map + commit
  check`, so the PR sets `"commit_check": true` in `.codemap.json`; the git hook is per clone, so
  the final report gives the owner `<cmd> install-hook` (off: `<cmd> uninstall-hook`) to run in
  their clone. Never install it yourself or let an agent do it. No → `Setup: code map`.

**Setup PR.** Install Python if the owner said yes, then land the setup PR before any phase (and
before a step-0 plan-only PR): a new implementer and reviewer, each with the `Setup` field, the
command (or `none`), phase `none` and `Branch: setup/code-map` (or the designated branch), through
steps 2 to 5 like a plan-only PR (fix rounds and brakes included; with a designated branch, step
5's reconcile before the next dispatch). It carries `Plan records: none`: pending records ride the
next phase or plan-only PR. A remote `setup/code-map` branch with no open PR, or with only a PR
closed unmerged, is abandoned: report it and use `setup/code-map-<run-id>`. Then every dispatch
gets the command. If the setup PR blocks or can't land: on a `setup/code-map*` branch, report why,
use `Code map: none` and go on with the phases; on a single designated branch it occupies the
branch (**Sequential phases**): stop and report.
