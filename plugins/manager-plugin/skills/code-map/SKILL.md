---
name: code-map
description: Build, check or query a project's generated code map and vault index with the plugin's standard-library Python script. It finds an existing vault wherever it is, including ones made without this plugin, and offers to install Python if it is missing. Use when the owner asks for a code map or a faster vault read, to find where something is defined or who imports a file, or when create-vault or the manager needs the map.
---

# Code map

A generated map of the repository, so agents read one page to see where to look and then run a
targeted `grep` instead of exploring. It contains:
- a directories table, entry points, the most imported files, and the top-level symbols per file;
- for the vault: an index of every page (path, title, words, how many pages link to it), broken
  links and orphan pages. An agent reads this one table instead of opening pages to find the
  right one.

It is produced by `scripts/codemap.py`, a Python 3.8+ script that uses only the standard library:
- files come from `git ls-files`;
- symbols are top-level definitions from line patterns, the same on every Python version
  (approximate); none are listed for tests;
- imports are local and parsed only for Python, JavaScript and TypeScript;
- files must be tracked: if `git ls-files` fails in a repository (e.g. Windows "dubious
  ownership"), it stops with an error instead of guessing;
- files that may hold secrets (`.env`, keys, `secrets` or `credentials` paths) are never read;
- vault pages are scanned outside code blocks for `[[links]]`, `[text](page.md)` links, and code
  spans that name a tracked file;
- it runs no project code and sends nothing anywhere.

## Where it writes

`.codemap.json` at the repository root (`{"vault": ..., "map": ...}`) fixes the layout. Without
it, the script detects the vault, trying in order:
1. a folder holding `.obsidian/`;
2. a known name: `docs/vault`, `vault`, `docs/knowledge`, `knowledge`, `docs/wiki`, `wiki`,
   `docs/notes`, `notes`, `kb`;
3. the folder holding most of the pages with `[[wikilinks]]` (at least 5).

Where the map goes:
- **With a vault:** `<vault>/map.md`. If a hand-written `map.md` is already there, it is never
  overwritten and the map goes to `<vault>/code-map.md`.
- **Without a vault:** `docs/code-map.md`.

The first `build` writes `.codemap.json`. Commit it with the map so every later run, on any
machine, agrees. `build --redetect` re-detects the layout, for example after a vault is created.

## Command

Resolve once per session:
- **Script:** `${CLAUDE_SKILL_DIR}/scripts/codemap.py`. Quote the path; it may contain spaces on
  Windows.
- **Python:** the first of `python3`, `python` and `py -3` whose `--version` exits 0 and prints
  `Python 3.8` or later. On Windows, `python3` may be a store stub that fails this check.

No Python → offer to install it, once, with the command for the OS. Install only after the owner
agrees in this conversation; if they decline, skip the map (nothing else depends on it).
- **Windows:** `winget install -e --id Python.Python.3.12 --scope user` (no admin rights needed).
  The current session's PATH may not see it yet. Check
  `"$LOCALAPPDATA/Programs/Python/Python312/python.exe" --version` and use that path; if it isn't
  there, say that a new session will pick Python up.
- **macOS:** `brew install python` if Homebrew exists, else the installer from python.org (the
  owner runs it).
- **Linux:** `sudo apt-get install -y python3` or the distribution's equivalent (the owner runs
  it).

`<cmd>` below is `<python> "<script>"`, run from the project root.

- `<cmd> detect`: the vault and map paths, and how they were found.
- `<cmd> build`: writes the map. Above 150 source files it adds one page per directory group of
  at most 150 files, splitting large directories by subdirectory, and above 150 vault pages a
  separate vault-pages page. It deletes map pages it generated earlier
  that are now gone. It touches no other file except `.codemap.json` on the first run.
- `<cmd> check`: exit 0 if the map matches the repository, 1 if it is stale. It writes nothing,
  so it is safe on a shared checkout. It also prints broken vault links as warnings.
- `<cmd> query <term>`: definitions whose names contain the term (`file:line`), matching paths,
  the files that import them, and the vault pages that mention them. Use it before a broad
  `grep`.
- `<cmd> mentions --base <sha>` (or `mentions <path>...`): the vault pages that mention, in a code
  span, any file changed since that commit. These are the pages to check after a change.

## Setting it up in a repository

Run `detect` and show the owner the result. If they agree, run `build` and land `.codemap.json`
with the map through a small PR. For a vault, also add a `[[map]]` line (or the map's file name)
to the vault's index page if it has one. This works the same for a vault the `create-vault`
skill made, one the owner had made in another session, or an Obsidian vault.

## Rules

- The map pages are generated. Never edit them by hand, review their wording, or give them a
  `Verified` line; `check` is their review.
- The map is navigation, not truth: open the file before relying on a symbol or a page.

## In the manager

When the project has `.codemap.json` and Python is available, the manager gives implementers and
reviewers `Code map: <cmd>`:
- the implementer runs `build` before its final validation and commits the result (not in a
  plan-only PR), and again after any integration;
- the reviewer runs `check` as required validation (stale means CHANGES REQUIRED), reads the diff
  without the map pages, and uses `mentions` to find the vault pages to check;
- a merge conflict in map pages is resolved by running `build` again, never by hand.
