---
name: code-map
description: Build, check or query a project's generated code map and vault index with the plugin's standard-library Python script. It finds an existing vault wherever it is, including ones made without this plugin, and offers to install Python if it is missing. Use when the owner asks for a code map or a faster vault read, to find where something is defined or who imports a file, or when create-vault or the manager needs the map. Also sets up its opt-in commit hooks (git pre-commit, Claude Code commit check) and the rules-file block that tells sessions to use the map; a default-on hook nudges a session's first broad search toward `query`.
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

`.codemap.json` at the repository root (`{"vault": ..., "map": ...}`) fixes the layout. Detecting
the layout (no `.codemap.json` yet, `detect`, the first `build`, `build --redetect`), where the map
goes, or a `build` refused over the layout: read `references/layout.md` first.

## Command

Resolve once per session:
- **Script:** `${CLAUDE_SKILL_DIR}/scripts/codemap.py`. Quote the path; it may contain spaces on
  Windows.
- **Python:** the first of `python3`, `python` and `py -3` whose `--version` exits 0 and prints
  `Python 3.8` or later. On Windows, `python3` may be a store stub that fails this check.

No Python → read `references/python-install.md` first (the install offer).

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
  `check --quiet`: the same full check and exit codes, one short line or nothing.
- `<cmd> query <term>`: definitions whose names contain the term (`file:line`), matching paths,
  the files that import them, the vault pages that mention them, and vault pages whose path or
  title matches. Use it before a broad `grep` or opening vault pages.
- `<cmd> mentions --base <sha>` (or `mentions <path>...`): the vault pages that mention, in a code
  span or a link, any file changed, deleted or renamed since that commit (compared with the working
  tree, so run it at the candidate), or a directory holding one. These are the pages to check
  after a change; also `grep` the vault for symbol names and plain-text paths the change renames
  or removes, since `mentions` sees only code spans and links.
- `<cmd> changed --base <base> --head <head>`: pointers for reviewing `git diff <base>...<head>`,
  at most 60 lines, then a count of the cut. Per changed file (map pages left out): the
  top-level definitions whose text differs (approximate: a change between two names the one
  above; `(module level)`: above the first), its importers, its tests (importing or named after
  it) and the vault lines mentioning it. Beyond the definitions it reads the working tree, so
  run it at `<head>`. It writes nothing. Pointers only, never a filter: it can miss what a
  change affects.

- `<cmd> rules-hint` (`--remove` to take it out): writes the rules block (`references/setup.md`)
  into `AGENTS.md` and `CLAUDE.md` at the repository root (each created if missing, with a one-line
  title).
- `<cmd> install-hook` / `uninstall-hook`: the git commit hook (`references/commit-hooks.md`).

## Setting it up in a repository

Setting the map up in a repository (with a vault and the rules block, in one PR), writing **The
rules block** by hand, or a rules block that is outdated: read `references/setup.md` first.

## Keeping it current: the commit hooks (opt-in)

Work outside a manager phase skips `build`, so the map can go stale. Two hooks guard it at commit
time. Both are off until the owner turns them on; turn one on only after the owner says yes.

Turning the **Git pre-commit hook** or the **Claude Code commit check** on or off, or a commit one
of them stopped or blocked: read `references/commit-hooks.md` first.

## Map first: the search nudge (on by default)

The rules block is advice, and sessions still start with broad `grep` and glob searches. The
plugin's `PreToolUse` hook on Grep, Glob and Bash (`hooks/codemap-search-nudge.sh`, logic in
`scripts/search_nudge.py`) makes the first one a nudge:
- It acts only in a repository (the session's working directory, up to the folder holding `.git`)
  whose `.codemap.json` is a plain file with a `map`. Everywhere else it does nothing.
- The first broad search of a session is blocked once, with one line: run this skill's
  `query <term>` (or read the vault index or the map page) first, and if that doesn't answer it,
  repeat the search, which is then allowed. Every later search in that session is allowed. The
  line names the runnable command, `<python> "<plugin>/skills/code-map/scripts/codemap.py" query
  <term> --root "<repo top>"` (the Python the wrapper found; the plugin folder from
  `CLAUDE_PLUGIN_ROOT`; quoted, forward slashes on Windows; `--root` keeps answers repo-wide
  from a subfolder), so agents without the Skill tool can run it; when that path can't be
  resolved it names the skill instead.
- A `codemap.py query` or `mentions` run earlier in the session counts as using the map: no block.

Turning it off, its state files, how it fails open, what counts as broad and its known gaps (a
search it blocked or allowed unexpectedly): read `references/search-nudge.md`.

## Rules

- The map pages are generated. Never edit them by hand, review their wording, or give them a
  `Verified` line; `check` is their review.
- The map is navigation, not truth: open the file before relying on a symbol or a page.
- A merge conflict in map pages: resolve the inputs (source files, vault pages), then run `build`
  again and stage its pages. Never edit them by hand.

## In the manager

At the start of every run, whatever the model strategy, the manager checks that the default branch
has a vault, `.codemap.json` with a `map` and the rules block. With no vault, it asks the owner
once whether to set one up (yes / not this time / never in this repo; "never" is recorded as an
owner decision in the plan); with a vault, it sets up what is missing without asking. Either lands
first as one small, reviewed setup PR, and the commit hooks are a separate yes in the same
question. With the map set up, it gives implementers and reviewers `Code map: <cmd>`:
- the implementer runs `build` before its final validation and commits the result (not in a
  plan-only PR), and again after any integration;
- the reviewer runs `check` as required validation (stale means CHANGES REQUIRED; not for a
  plan-only PR), reads the diff without the map pages, runs `changed` for pointers (never a
  filter), and uses `mentions` plus a grep for renamed or removed names and paths to find the
  vault pages to check;
- a merge conflict in map pages is resolved by running `build` again, never by hand.
