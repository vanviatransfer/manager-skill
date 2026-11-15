# Code-map setup PR

Read when the dispatch has `Setup: code map`.

**Implementer.** On the dispatch's branch: run `<code map> build` (`build --redetect`, with
`--vault <its vault>` if it names one, when a `.codemap.json` exists without a `map`), add one
line for the map to the vault's index page if it has one (never the living plan or a rules file),
commit only `.codemap.json`, the generated pages and that line; its validation is `<code map>
check`, plus any validation the project rules require for every PR. The phase-PR plan, vault and
skill-record edits don't apply.

**Reviewer**, instead of the phase-PR review: blocker if the diff holds anything but
`.codemap.json`, generated map pages and one vault index line (never in the living plan or a rules
file), or if `<code map> check` fails; its required validation is that `check`, plus any
validation the project rules require for every PR.
