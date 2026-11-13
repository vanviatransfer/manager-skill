---
name: code-map
description: Build, check or query a project's generated code map (docs/vault/map.md, plus one page per directory in large repos) with the plugin's standard-library Python script (it offers to install Python if missing). Use when the owner asks for a code map, to find where something is defined or who imports a file, or when create-vault or the manager needs the map.
---

# Code map

A generated map of the code: a directories table, entry points, the most imported files, per file
its top-level symbols, and, for the vault, its broken links and orphan pages. Agents read it to see
where to look, then use a targeted `grep` instead of exploring the code. It is produced by
`scripts/codemap.py`, a Python 3.8+ script that uses only the standard library:
- files come from `git ls-files`;
- Python symbols come from `ast`, other languages from line patterns (approximate);
- no symbols are listed for tests;
- imports are local only;
- files that may hold secrets (`.env`, keys, `secrets`/`credentials` paths) are never read;
- vault pages are scanned outside code blocks for `[[links]]`, `[text](page.md)` links and code
  spans that name a tracked file;
- it runs no project code and sends nothing anywhere.

## Command

Resolve once per session:
- **Script:** `${CLAUDE_SKILL_DIR}/scripts/codemap.py`. Quote the path, since it may contain
  spaces on Windows.
- **Python:** the first of `python3`, `python` and `py -3` whose `--version` exits 0 and prints
  `Python 3.8` or later. On Windows, `python3` may be a store stub that fails this check.

No Python → offer to install it, once, with the command for the OS. Install only after the owner
agrees in this conversation; if they decline, skip the map (nothing else depends on it).
- Windows: `winget install -e --id Python.Python.3.12 --scope user` (no admin rights needed).
  The current session's PATH may not see it yet. Check
  `"$LOCALAPPDATA/Programs/Python/Python312/python.exe" --version` and use that path; if it isn't
  there, say a new session will pick Python up.
- macOS: `brew install python` if Homebrew exists, else the installer from python.org (owner).
- Linux: `sudo apt-get install -y python3` or the distribution's equivalent (the owner runs it).

`<cmd>` below is `<python> "<script>"`, run from the project root.

- `<cmd> build`: writes `docs/vault/map.md`. Above 150 source files it also writes
  `docs/vault/map/<dir>.md`, one page per top-level directory, and deletes map pages it generated
  earlier that are gone. It never touches other files.
- `<cmd> check`: exit 0 if the map matches the code, 1 if it is stale. It writes nothing, so it is
  safe on a shared checkout.
- `<cmd> query <term>`: the definitions whose names contain the term (`file:line`), the matching
  paths, the files that import each match, and the vault pages that mention it. Use it before a
  broad `grep`.
- `<cmd> mentions --base <sha>` (or `mentions <path>...`): the vault pages that mention, in a
  code span, any file changed since that commit. These are the pages to check after a change.

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
