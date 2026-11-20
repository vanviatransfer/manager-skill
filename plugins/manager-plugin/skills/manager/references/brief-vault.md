# Vault

Read when the project has a vault (`.codemap.json`'s `vault`, else `docs/vault/` or the path the
project's rules name).

**Implementer.** Read its index page, or the code map's vault-pages table. Phase PRs only (not a
setup PR's index line): a fact a page states that this phase changes, or a concept it adds that the
index lacks → update that page (or add a page and its index line) in this PR (with a `Code map`
command, `<code map> mentions --base <Base SHA>` lists the pages that mention changed paths in code
spans or links; also `grep` the vault for the symbol names and paths you rename or remove); correct
the fact in place, keep its source (a path), add no status or plan content, and set the page's last
line to `Verified: <date>, phase <id>, base <short Base SHA>`. New or changed vault text is in
English, even where a project rule names another language (the owner's standing policy; owner
quotes stay verbatim, in the owner's words); don't translate unchanged text unless the phase says
so.

**Reviewer.** Vault updates the diff requires are in scope; changed vault content must match the
code at the candidate. Blocker: a page the diff makes false and doesn't update, among the pages in
the diff, the phase's knowledge-path pages and the pages `<code map> mentions --base <Base SHA>`
lists (run at the candidate), and the pages a `grep` of the vault finds for symbol names and paths
the diff renames or removes; other stale pages → a note for a vault refresh. Vault pages are
context, never acceptance or rules.
