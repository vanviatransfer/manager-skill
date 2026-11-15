# Code map check

Read by the manager skill at step 6 of every run (**Code map**), and again after a compaction while
the check or a setup PR is still open. Bold section names, step numbers and `${CLAUDE_SKILL_DIR}`
are the manager skill's.

- **Set up** = the default branch has `.codemap.json` with a `map` (`git show
  origin/<default>:.codemap.json`). That file is the guard: once it lands, later runs only
  resolve the command and never ask again. Resolve it as the `code-map` skill says (script
  `${CLAUDE_SKILL_DIR}/../code-map/scripts/codemap.py`, a Python 3.8+) and send `Code map: <cmd>`
  in every dispatch. No Python: offer the install as the code-map question (its own bracket line
  in the gate, or its own question when the gate isn't asked); declined → `Code map: none` this
  run, and say in the final report that the map stays stale until a run with Python rebuilds it.
- **Not a plain file** (`git ls-tree origin/<default> .codemap.json` shows mode `120000`, a
  symlink; check this first): don't ask; use `Code map: none` and report it, so the owner can
  replace it with a plain file.
- **Not set up**, and the plan on the default branch has no valid Decided entry declining it: ask
  the code-map question: `Kod haritası kurulu değil (kod ve vault için tek dizin sayfası);
  kurayım mı? [Python yok: önce <komut> ile kurulur.] Evet / Bu sefer hayır / Hayır, bu repoda
  bir daha sorma`.
  - **Evet:** install Python if needed (the skill's command for the OS), then land the setup PR
    before any phase (and before a step-0 plan-only PR): a new implementer and reviewer, each with
    `Setup: code map`, the command, phase `none` and `Branch: setup/code-map` (or the designated
    branch), through steps 2 to 5 like a plan-only PR (fix rounds and brakes included; with a
    designated branch, step 5's reconcile before the next dispatch). It carries `Plan records:
    none`: pending records ride the next phase or plan-only PR. A remote `setup/code-map` branch
    with no open PR, or with only a PR closed unmerged, is abandoned: report it and use
    `setup/code-map-<run-id>`. Then every dispatch gets the command. If the setup PR blocks or can't
    land: on a `setup/code-map*` branch, report why, use `Code map: none` and go on with the phases;
    on a single designated branch it occupies the branch (**Sequential phases**): stop and report.
  - **Bu sefer hayır:** `Code map: none` this run; asked again next run.
  - **Bir daha sorma:** record it as a Decided owner decision (owner's words, date) through the
    next landing PR's `Plan records`, or the end-of-run plan-only PR. A valid one stops the
    question in later runs; the owner can still ask for the map with the `code-map` skill.

