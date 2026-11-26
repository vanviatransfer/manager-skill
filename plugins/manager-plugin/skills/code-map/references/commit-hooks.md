# The commit hooks (opt-in)

Read by the code-map skill when turning a commit hook on or off (only after the owner says yes),
or when one of them stopped or blocked a commit.

**Git pre-commit hook** (per clone; `.git/hooks` isn't versioned, so every clone runs it once):
- on: `<cmd> install-hook`; off: `<cmd> uninstall-hook`. Both are safe to run again.
- When the staged changes touch the map's inputs (source files, vault pages, `package.json`,
  `.codemap.json`, an added or removed tracked file, or the map pages), it runs `build` and stages
  only the regenerated map pages, so they land in the same commit. A commit touching none of them
  runs no build.
- It stops the commit, with a one-line reason, when an input has unstaged changes (the map would
  be built from the working tree: stage or stash them, then commit; the raw bytes of every input
  are compared with the staged ones, so assume-unchanged, skip-worktree and clean filters can't
  hide a change, while a CRLF-only difference doesn't count), when a tracked input isn't a
  readable file in the working tree (sparse checkout, skip-worktree, deleted: check it out, or
  run `build` in a full checkout and commit with `--no-verify`), when `build` refuses (exit 2: a
  hand-written file in the map's page folder, an invalid layout), or for `git commit <paths>` /
  `--only` when the map needs a rebuild (git can't take the map pages into that commit: stage the
  files and commit without paths).
- It is a POSIX `sh` script (Git for Windows runs hooks through its own `sh`, also for a commit
  started from PowerShell). It finds Python as the skill's **Command** says and runs this script
  by the path it had at install time, or else the newest plugin version beside it (only folders
  named like a version number, outside any git work tree); with no Python or no script it warns
  and lets the commit through.
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
  that key. It runs `check --quiet` and blocks the commit while the map is stale, or rebuilt but
  not staged, with one line: run `build`, then `git add` the pages it names, each as its own
  command, then commit again. It runs before the command starts, so `build && git add && git
  commit` in one command stays blocked. When this clone has the git hook, it leaves the refresh
  to that. No key, no `.codemap.json`, no Python or any error: it does nothing. Known gaps,
  where it also does nothing: it can't be sure which repository commits (`cd` / `pushd`,
  `git -C <dir>`, `--git-dir` or `--work-tree` before the commit, `GIT_DIR=... git commit`,
  `env git commit`, `/usr/bin/git commit`, a commit inside `sh -c "..."` or a script; `git` must
  stand in command position, so `echo git commit` is no commit). Another: it judges the working
  tree's inputs, not the staged ones, so unrelated unstaged edits can block a commit, and the
  `build` it asks for maps them too (stash them first, or use the git hook, which refuses
  instead).
