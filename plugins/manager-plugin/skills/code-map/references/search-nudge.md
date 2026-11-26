# The search nudge: state, switch, failures, what counts as broad

Read by the code-map skill when turning the search nudge off, or when it blocked or allowed a
search unexpectedly.

- Each subagent counts on its own: the state key is the hook input's `session_id`, its `agent_id`
  (set inside a subagent) and `transcript_path`, plus the repository's top folder. The state is an
  empty marker file under the OS temp folder (`manager-plugin-search-nudge-<uid>`, mode 700, files
  600, entries older than 7 days are pruned), never inside the repository. The temp folder is the
  first existing one of `TMPDIR`, `TEMP`, `TMP` and the OS defaults, never the working directory.
- Off: set `"search_nudge": false` in `.codemap.json` and commit it.
- It fails open: no Python, no session id, invalid JSON, an unreadable or unwritable state folder
  (a symlink, one not owned by you alone on POSIX, or one that would fall inside any repository
  or the hook's working directory) or any
  other error allows the search. Without a search command in the input it doesn't start Python
  (about 4 ms); otherwise about 25–35 ms.

What counts as broad (kept simple; when unsure it allows):
- Broad: a search whose path resolves to the repository root or a top-level folder. No path means
  the working directory (after a `cd <dir>` in the same command, that folder). For Glob, a pattern
  that reaches `**` from there (`**/*.py`, `src/**/*.ts`).
- Narrow: a file, a path two or more levels deep, the vault folder, the map page or its page
  folder, a path outside the repository, a pattern for specific files (`grep -r x *.py`, Glob
  `*.md`), and paths with `$` or `~`.
- Bash: `grep` / `egrep` / `fgrep` only with `-r` / `-R`; `rg`, `ag`, `ack`, `find` and
  `git grep`, in command position (line start, or after `;`, `&`, `|`, `(`, a backtick or a
  newline), outside quotes, so `echo "grep x"` is no search. `rg`, `ag` and `ack` without a path
  after a pipe read stdin and don't count; `find -maxdepth 0|1` is a listing.

Known gaps, where it allows: `git -C`, `--git-dir`, `--work-tree`, `cd -`, `cd ~` or `cd $X`
before the search; searches inside `sh -c "..."`, `"$(...)"`, `xargs` or scripts; a revision
operand of `git grep` (`git grep foo HEAD`) taken for a path; `fd`, `ls -R` and other tools. A
here-document's lines still count as commands.
