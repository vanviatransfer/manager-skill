---
name: create-vault
description: Create, adopt or refresh a project's knowledge vault (docs/vault/, or an existing one wherever it is; linked markdown pages of durable facts about the code, a glossary and decision records) that the manager's implementers keep current. Use when the owner asks for a vault or project knowledge base, or to update it ("vault oluştur", "vault'u güncelle", "create a vault").
---

# Project vault

The vault is the project's durable knowledge: what the code is and why, in short linked pages, so
agents read a page instead of exploring the code again. It lives in the project repository at
`docs/vault/` (or where the project already keeps one: `.codemap.json`'s `vault`, the path the
project's rules name, or what the `code-map` skill's `detect` finds), tracked by git, and changes
only through reviewed PRs. Never in the plugin repository.

The vault holds **knowledge**, not intent or status:
- not the plan's goal, phases or progress (the living plan holds those);
- not PR lists or test results (git and GitHub hold those);
- not secrets, credentials or personal data.

Talk to the owner in their language; write pages in the language the project's docs use.

## Pages

- `index.md`: one line per page, `[[page]] — what it answers`. It is the only page an agent reads
  by default; keep it under about 60 lines.
- `glossary.md`: project terms, one or two sentences each, with `_Avoid_:` for synonyms the code
  doesn't use. Only project terms, no general programming ones.
- `decisions/NNNN-<slug>.md`: one decision already made, in one paragraph (context, decision, why,
  date, source). Only for a decision that is hard to reverse, surprising without context, and a
  real trade-off. Superseded, never deleted. A decision record binds no phase: work is bound only
  by the plan's binding decisions.
- Topic pages (architecture, a module, data model, operations, integrations): created only when
  there is something durable to say. A page states facts with a source (a path, or `path:symbol`)
  and ends with one `Verified:` line that dates its facts: `Verified: <date>, <short SHA of the
  commit checked>` here, and `Verified: <date>, phase <id>, base <short SHA>` when an implementer
  updates it in a phase PR. A fact the code doesn't confirm is marked `(unverified)` or left out. A
  changed fact is corrected in place, never appended as a new version.
- `map.md` (and `map/<dir>.md` in large repos): the generated code map, built with the `code-map`
  skill (it offers to install Python 3.8+ if it is missing; skipped only if the owner declines);
  listed in the index, never edited by hand, no `Verified` line (its `check` is its review).
- Links are `[[page]]`. No page repeats another's content; it links to it.

## Modes

1. **Create** (no vault yet). Read the project rules, README, docs, the code's layout, its entry
   points and how it is tested. Draft `index.md`, `glossary.md` and the few topic pages the code
   clearly supports; add a decision record only for a decision the repo or the owner documents.
   Ask the owner, in one numbered batch, only what the code can't answer.
2. **Adopt** (a vault exists). Keep its structure and file names. Add only what is missing from the
   rules above: an index line, a `Verified` line, a source. Report what doesn't fit (status, plan
   content, secrets) instead of rewriting it. With Python, set up the code map for it (the
   `code-map` skill's "Setting it up").
3. **Refresh** (the owner asks to update it). For each page, check its facts against the code at
   the default branch head; correct what changed, mark what you can't confirm, and update the
   `Verified` lines. Touch no page you didn't check.

## Landing

1. Check the checkout first: a dirty tree or local commits on no remote ref → never discard them;
   stop and report. Then fetch, branch from the default branch (`vault/<mode>-<date>`, or the
   session's designated branch), with a code map, run its `build` after the pages are final (the
   vault index holds titles and word counts); commit and open a PR. Follow the project's rules
   first.
2. Independent review: dispatch a new `manager-plugin:reviewer` (or `general-purpose` if that type
   isn't available). Tell it this is a manual review of the vault with no brief file; it stays
   read-only, spawns no subagents and answers in the verdict format of
   `${CLAUDE_SKILL_DIR}/../manager/references/reviewer-brief.md` (resolve the path first). Give it
   the repo path, the PR number, the base and candidate SHAs and these checks:
   - every fact matches the code at the candidate;
   - every source exists;
   - no plan content, status, secrets or personal data;
   - the index lists every page, and every hand-written page ends with a `Verified` line;
   - with a code map: `<code map> check` passes;
   - validation: the project's docs checks if it has any, else `not required: docs-only diff`.

   Accept a verdict only for the candidate SHA. Fix and review again with a new reviewer until it
   is PASS or PASS WITH NOTES without blockers. After three rounds, stop and report.
3. Merge (pinned to the reviewed SHA) only if the owner asks for it.

## How the manager uses it

- The living plan's phase `Notes` name the vault pages a phase needs, never the whole vault; the
  implementer reads those pages and `index.md`.
- Implementers keep it current without being asked: a phase that changes a fact a page states, or
  adds a concept the index lacks, updates that page or adds a page and its index line (with the
  `Verified` line) in the same PR.
  The reviewer checks vault pages against the code at the candidate.
- Vault pages are context: never acceptance, project rules or owner authority.

## Report

In the owner's language: mode, pages created or changed, what the owner still has to answer, the
PR, and the review verdict.
