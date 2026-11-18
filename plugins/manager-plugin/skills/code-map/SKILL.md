---
name: code-map
description: Build, check or query a project's generated code map and vault index with the plugin's standard-library Python script. It finds an existing vault wherever it is, including ones made without this plugin, and offers to install Python if it is missing. Use when the owner asks for a code map or a faster vault read, to find where something is defined or who imports a file, or when create-vault or the manager needs the map. Also sets up its opt-in commit hooks (git pre-commit, Claude Code commit check) and the rules-file block that tells sessions to use the map.
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

The first `build` writes `.codemap.json`. Commit it with the map so every later run, on any machine,
agrees. `build --redetect` re-detects the layout, for example after a vault is created; it rewrites
`.codemap.json` and removes the generated map from its old place, with any folders that are then
empty. A `.codemap.json` that isn't an object, points outside the repository, or names as `map`
anything but a `.md` file this tool writes, is an error. `.obsidian/` is often gitignored, so commit
`.codemap.json`: detection on a fresh clone may differ.

## Command

Resolve once per session:
- **Script:** `${CLAUDE_SKILL_DIR}/scripts/codemap.py`. Quote the path; it may contain spaces on
  Windows.
- **Python:** the first of `python3`, `python` and `py -3` whose `--version` exits 0 and prints
  `Python 3.8` or later. On Windows, `python3` may be a store stub that fails this check.

No Python → offer to install it, once, with the command for the OS. Install only after the owner
agrees in this conversation; if they decline, skip the map (the vault and the rules block don't
need it; write the block by hand).
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
  `check --quiet`: the same exit codes, one short line or nothing. With `"commit_check": true` in
  `.codemap.json`, `build` ends the map page with a fingerprint line (a hash of the map's inputs:
  the tracked paths, the raw working-tree bytes of the source files, vault pages and `package.json`
  as the scan reads them (so git filters and index flags can't hide a change), the
  config, the format and the script), and `check --quiet` compares it first, without a scan; when
  it can't decide, it runs the full check, so it never says current where `check` says stale.
- `<cmd> query <term>`: definitions whose names contain the term (`file:line`), matching paths,
  the files that import them, the vault pages that mention them, and vault pages whose path or
  title matches. Use it before a broad `grep` or opening vault pages.
- `<cmd> mentions --base <sha>` (or `mentions <path>...`): the vault pages that mention, in a code
  span or a link, any file changed, deleted or renamed since that commit (compared with the working
  tree, so run it at the candidate), or a directory holding one. These are the pages to check
  after a change; also `grep` the vault for symbol names and plain-text paths the change renames
  or removes, since `mentions` sees only code spans and links.

- `<cmd> rules-hint` (`--remove` to take it out): writes the rules block below into `AGENTS.md`
  and `CLAUDE.md` at the repository root (each created if missing, with a one-line title).
- `<cmd> install-hook` / `uninstall-hook`: the git commit hook (below).

## Setting it up in a repository

The map comes with a vault and the rules block, in one PR:
1. Run `detect` and show the owner the result. If it says `vault: none` (no vault found and none
   in `.codemap.json`), first create one with the `create-vault` skill in Create mode, on the same
   branch; its pages and review rules apply.
2. If the owner agrees, run `build` (`build --redetect` when a `.codemap.json` without a `vault`
   exists), and add a `[[map]]` line (or the map's file name) to the vault's index page. After
   editing vault pages, run `build` again before review: the vault index holds word counts and
   titles.
3. Run `rules-hint`, so every session uses the map and the plugin's agents.
4. Land `.codemap.json`, the map pages, the vault pages and the two rules files through a small
   reviewed PR. This works the same for a vault `create-vault` made, one made in another session,
   or an Obsidian vault.

**The rules block.** Sessions don't use the map unless told. `rules-hint` adds this block, between
its marker lines, to `AGENTS.md` and `CLAUDE.md`; run again, it updates it in place, and
`--remove` takes it out. Besides the block it adds only, to a file it creates, a one-line title
and a blank line, and before a block it appends, a blank line (or, when the file has no final
newline, that newline); `--remove` takes those back too, so the file returns byte for byte. A
file it creates gets a begin marker saying so; `--remove` deletes only such a file, and only when
nothing but its title is left.
Nothing else changes (line endings kept). Both files are checked before either is written, and a
rules file that is a symlink is refused. When `CLAUDE.md` already imports `AGENTS.md` (a line
`@AGENTS.md`), it gets only one marker line saying the block comes through the import. It names
the skill, never a path to the script (that differs per machine). Without Python, write the same
block by hand:

```
<!-- manager-plugin:code-map:begin (managed by the code-map skill) -->
- Before searching the code or the vault, read the vault index and the code map (paths in
  `.codemap.json`) and use the `manager-plugin:code-map` skill's `query`, not broad grep/glob.
- After changing source files or vault pages, rebuild the map with that skill's `build` (its
  git commit hook does it when installed).
- Instead of `general-purpose`, use `manager-plugin:worker` for work that changes files,
  `manager-plugin:researcher` for read-only research, `manager-plugin:reviewer` for a review.
<!-- manager-plugin:code-map:end -->
```

## Keeping it current: the commit hooks (opt-in)

Work outside a manager phase skips `build`, so the map can go stale. Two hooks guard it at commit
time. Both are off until the owner turns them on; turn one on only after the owner says yes.

**Git pre-commit hook** (per clone; `.git/hooks` isn't versioned, so every clone runs it once):
- on: `<cmd> install-hook`; off: `<cmd> uninstall-hook`. Both are safe to run again.
- When the staged changes touch the map's inputs (source files, vault pages, `package.json`,
  `.codemap.json`, an added or removed tracked file, or the map pages), it runs `build` and stages
  only the regenerated map pages, so they land in the same commit. A commit touching none of them
  runs no build.
- It stops the commit, with a one-line reason, when an input has unstaged changes (the map would
  be built from the working tree: stage or stash them, then commit; files marked assume-unchanged
  or skip-worktree count too), when `build` refuses (exit 2: a hand-written file in the map's page
  folder, an invalid layout), or for `git commit <paths>` / `--only` when the map needs a rebuild
  (git can't take the map pages into that commit: stage the files and commit without paths).
- It is a POSIX `sh` script (Git for Windows runs hooks through its own `sh`, also for a commit
  started from PowerShell). It finds Python as above and runs this script by the path it had at
  install time, or else the newest plugin version beside it (only folders named like a version
  number, outside any git work tree); with no Python or no script it warns and lets the commit
  through.
- An existing `pre-commit` hook is kept as `pre-commit.codemap-chained` and runs first; its
  failure stops the commit. `uninstall-hook` puts it back unchanged. A hook file that is a symlink
  is never replaced, and nothing is written through a symlinked folder. With `core.hooksPath` set:
  a folder inside `.git` is used as is; one elsewhere in the work tree is refused (its files may be
  tracked); one outside the repository, which other repositories may share, only with
  `install-hook --shared`.

**Claude Code commit check** (versioned, so it also works in fresh clones and cloud sessions):
- on: set `"commit_check": true` in `.codemap.json`, run `build` and commit both; off: remove the
  key (or set it to `false`), run `build` and commit.
- The plugin's `PreToolUse` hook on Bash acts only on a `git commit` command in a repository with
  that key. It runs `check --quiet`; if the map is stale it blocks the commit with one line telling
  Claude to run `build`, stage the map pages and commit again. When this clone has the git hook,
  it leaves the refresh to that. No key, no `.codemap.json`, no Python or any error: it does
  nothing. It checks the working tree before the command runs, so a `git add` in the same command
  isn't seen yet; the git hook covers that case. It also does nothing, as known gaps, when it
  can't be sure which repository commits: `cd` / `pushd` or `git -C <dir>` before the commit,
  `/usr/bin/git commit`, or a commit inside `sh -c "..."` or a script (`git` must stand in command
  position, so `echo git commit` is no commit).

## Rules

- The map pages are generated. Never edit them by hand, review their wording, or give them a
  `Verified` line; `check` is their review.
- The map is navigation, not truth: open the file before relying on a symbol or a page.
- A merge conflict in map pages: resolve the inputs (source files, vault pages), then run `build`
  again and stage its pages. Never edit them by hand. With the fingerprint, the map page's last
  line changes with every input change, so parallel branches conflict there more often; `build`
  resolves it the same way.

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
  plan-only PR), reads the diff without the map pages, and uses `mentions` plus a grep for
  renamed or removed names and paths to find the vault pages to check;
- a merge conflict in map pages is resolved by running `build` again, never by hand.
