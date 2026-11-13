---
name: code-map
description: Build, check or query a project's generated code map (docs/vault/map.md, plus one page per directory in large repos) with the plugin's dependency-free script; nothing is installed. Use when the owner asks for a code map, to find where something is defined or who imports a file, or when create-vault or the manager needs the map.
---

# Code map

A generated map of the code: a directories table, entry points, the most imported files, and
per file its top-level symbols. Agents read it to see where to look, then use a targeted `grep`
instead of exploring the code. It is produced by `scripts/codemap.py`, a Python 3.8+ script that
uses only the standard library:
- files come from `git ls-files`;
- Python symbols come from `ast`, other languages from line patterns (approximate);
- no symbols are listed for tests;
- imports are local only;
- it runs no project code and sends nothing anywhere.

## Command

Resolve once per session:
- **Script:** `${CLAUDE_SKILL_DIR}/scripts/codemap.py`. Quote the path, since it may contain
  spaces on Windows.
- **Python:** the first of `python3`, `python` and `py -3` whose `--version` exits 0 and prints
  `Python 3.8` or later. On Windows, `python3` may be a store stub that fails this check.

No Python → say so once and skip the map. Nothing else depends on it.

`<cmd>` below is `<python> "<script>"`, run from the project root.

- `<cmd> build`: writes `docs/vault/map.md`. Above 150 source files it also writes
  `docs/vault/map/<dir>.md`, one page per top-level directory, and deletes map pages it generated
  earlier that are gone. It never touches other files.
- `<cmd> check`: exit 0 if the map matches the code, 1 if it is stale. It writes nothing, so it is
  safe on a shared checkout.
- `<cmd> query <term>`: the definitions whose names contain the term (`file:line`), the matching
  paths, and the files that import each match. Use it before a broad `grep`.

## Rules

- The map pages are generated. Never edit them by hand, review their wording or give them a
  `Verified` line; `check` is their review.
- They belong to the vault: `index.md` lists `[[map]]`. A project with no vault can still keep the
  map at `docs/vault/map.md`.
- The map is navigation, not truth. Before relying on a symbol, open the file.

## In the manager

When the project has `docs/vault/map.md` and Python is available, the manager gives implementers
and reviewers `Code map: <cmd>`:
- the implementer runs `build` before its final validation and commits the result;
- the reviewer runs `check` as required validation, and stale means CHANGES REQUIRED;
- a merge conflict in map pages is resolved by running `build` again, never by hand.
