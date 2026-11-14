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
- files come from `git ls-files` (outside a git repository, from the folder tree; symlinks and
  tracked third-party or output folders such as `node_modules`, `vendor`, `third_party`, `dist`,
  `coverage` and `.venv` are skipped);
- symbols are top-level definitions from line patterns, the same on every Python version
  (approximate); none are listed for tests;
- imports are local and parsed only for Python, JavaScript and TypeScript;
- files must be tracked: if `git ls-files` fails in a repository (e.g. Windows "dubious
  ownership"), it stops with an error instead of guessing;
- files that may hold secrets (`.env`, keys, `secrets` or `credentials` paths) are never read;
- vault pages are scanned outside code blocks for `[[links]]`, `[text](page.md)` links, and code
  spans or links that name a path (a file, a directory, or one that no longer exists);
- it runs no project code and sends nothing anywhere.

## Where it writes

`.codemap.json` at the repository root (`{"vault": ..., "map": ...}`) fixes the layout. Without
it, the script detects the vault, trying in order:
1. a `.obsidian/` folder: at the repository root (the whole repository is the vault), else the
   shallowest folder holding one, up to three levels deep;
2. `docs/vault` or `vault`; or `docs/knowledge`, `knowledge`, `docs/wiki`, `wiki`, `docs/notes`,
   `notes`, `kb` or `docs/kb` when it has at least 3 pages and uses `[[wikilinks]]`;
3. the deepest folder holding at least 80% of the pages with `[[wikilinks]]` (at least 5 such
   pages).

Folders that may hold secrets are never read, not even for detection.

Where the map goes, taking the first location that is free (no file there, or one this tool
wrote, no symlink on the way, and no hand-written file in its page folder):
- **With a vault:** `<vault>/map.md` (`map.md` for a root vault), then `<vault>/code-map.md`, then
  `<vault>/code-map-generated.md`.
- **Without a vault:** `docs/code-map.md`, then `docs/code-map-generated.md`.

If none is free, it stops and asks for a `map` in `.codemap.json`. A hand-written file is never
overwritten, and inside the repository nothing is read or written through a symlink (on Windows
also a junction, with Python 3.12+), `.codemap.json` included. An explicit `--out` outside the
repository is the caller's choice; there only existing files are protected.

The first `build` writes `.codemap.json`. Commit it with the map so every later run, on any
machine, agrees. `build --redetect` re-detects the layout, for example after a vault is created; it
rewrites `.codemap.json` and removes the generated map from its old place. A `.codemap.json` that
isn't an object, points outside the repository, or names as `map` anything but a `.md` file this
tool writes, is an error. `.obsidian/` is often gitignored, so commit `.codemap.json`: detection on
a fresh clone may differ.

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
- `<cmd> build`: writes the map. Above 150 source files it adds one page per directory group,
  splitting directories with more than 150 files by subdirectory (files directly in one folder stay
  together; a page lists at most 800 files, then points to `query`), and above 150 vault pages a
  separate vault-pages page. It deletes map pages it generated earlier
  that are now gone. It touches no other file except `.codemap.json` on the first run, and it
  refuses (exit 2, nothing written) to overwrite a file it didn't write, including a hand-written
  page in the map's page folder.
- `<cmd> check`: exit 0 if the map matches the repository, 1 if it is stale, 2 if the layout is
  invalid (for example a hand-written file in the map's page folder) or git fails. It writes
  nothing, so it is safe on a shared checkout. It also prints broken vault links as warnings.
- `<cmd> query <term>`: definitions whose names contain the term (`file:line`), matching paths,
  the files that import them, the vault pages that mention them, and vault pages whose path or
  title matches. Use it before a broad `grep` or opening vault pages.
- `<cmd> mentions --base <sha>` (or `mentions <path>...`): the vault pages that mention, in a code
  span or a link, any file changed, deleted or renamed since that commit (compared with the working
  tree, so run it at the candidate), or a directory holding one. These are the pages to check
  after a change; also `grep` the vault for symbol names and plain-text paths the change renames
  or removes, since `mentions` sees only code spans and links.

## Setting it up in a repository

Run `detect` and show the owner the result. If they agree, run `build` and land `.codemap.json` with
the map through a small PR. After editing vault pages, run `build` again before review: the vault
index holds word counts and titles. For a vault, also add a `[[map]]` line (or the map's file name)
to the vault's index page if it has one. This works the same for a vault the `create-vault` skill
made, one the owner had made in another session, or an Obsidian vault.

## Rules

- The map pages are generated. Never edit them by hand, review their wording, or give them a
  `Verified` line; `check` is their review.
- The map is navigation, not truth: open the file before relying on a symbol or a page.

## In the manager

At the start of every run, whatever the model strategy, the manager checks whether the default
branch has `.codemap.json` with a `map`. That committed file is the guard: once it exists, the
check passes silently. Without it, the manager asks whether to set the map up (yes / not this time
/ never in this repo; "never" is recorded as an owner decision in the plan), and on yes lands the
setup first as its own small, reviewed PR. With the map set up, it gives implementers and reviewers
`Code map: <cmd>`:
- the implementer runs `build` before its final validation and commits the result (not in a
  plan-only PR), and again after any integration;
- the reviewer runs `check` as required validation (stale means CHANGES REQUIRED; not for a
  plan-only PR), reads the diff without the map pages, and uses `mentions` plus a grep for
  renamed or removed names and paths to find the vault pages to check;
- a merge conflict in map pages is resolved by running `build` again, never by hand.
