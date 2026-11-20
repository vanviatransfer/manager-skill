# Setup PR (vault, code map, rules block)

Read when the dispatch has `Setup: code map` (or `Setup: code map + commit check`). The paths
below are beside this file's folder: `../../create-vault/SKILL.md`, `../../code-map/SKILL.md`.
The plan has no phase section to read for it.

**Implementer.** On the dispatch's branch:
1. No vault (`<code map> detect` says `vault: none`; with `Code map: none`, no vault folder): create
   one as `create-vault`'s **Pages** and Create mode say. You can't ask the owner: leave out or
   mark `(unverified)` what the code doesn't answer, and list those questions in your report.
2. With a `Code map` command: `<code map> build` (`build --redetect`, with `--vault <its vault>`,
   when a `.codemap.json` exists without a `map` or a `vault`); add one line for the map to the
   vault's index page. With `+ commit check`: add `"commit_check": true` to `.codemap.json` and
   run `build` again. Never run `install-hook`.
3. `<code map> rules-hint` (it also replaces an outdated block); with `Code map: none`, write the
   block by hand (in place of an outdated one) from the `code-map`
   skill's **The rules block** template into `AGENTS.md` and `CLAUDE.md`, with the same separator
   lines `rules-hint` would add (nothing else changes there).
4. Commit by path only the vault pages, `.codemap.json`, the generated pages and the two rules
   files. Validation: `<code map> check` (none without a command), plus any validation the project
   rules require for every PR. The phase-PR plan, vault and skill-record edits don't apply.

**Reviewer**, instead of the phase-PR review: blocker if the diff holds anything but vault pages,
`.codemap.json`, generated map pages and the `rules-hint` edits of `AGENTS.md` / `CLAUDE.md`: the
marked block (in `CLAUDE.md` that imports `@AGENTS.md`, instead the one marker line
`<!-- manager-plugin:code-map: the code-map block comes via @AGENTS.md -->`), plus a new file's
one-line title and blank line, or the blank line (or missing final newline) before an appended
block (any other change in them, or in the living plan, is a
blocker); if `"commit_check": true` appears without
`+ commit check` in `Setup`; or if `<code map> check` fails. New or changed vault pages get
`create-vault`'s review checks (facts match the code at the candidate, sources exist, no plan
content, status, secrets or personal data, the index lists every page, every hand-written page
ends with a `Verified` line). Required validation: that `check`, plus any validation the project
rules require for every PR.
