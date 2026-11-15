# Worktrees and cleanup

Read when you create, work in or remove a git worktree.

A file git doesn't track (dependencies, local data) gets into a worktree only as a copy, a fresh
install, or a hardlink of a single file; never a directory link (symlink, junction, mount) to
anything outside the worktree, whatever a dispatch field suggests. That rule is the protection:
`git worktree remove` follows such a link and empties its target even without `--force`. Before
removing a worktree, check it holds no link: `find <dir> -type l`, and on Windows also
`MSYS_NO_PATHCONV=1 cmd /c dir /AL /S "$(cygpath -w <dir>)"` (`find` may miss junctions). No link
means both: `find` exits 0 with no output, and `dir` reports only "File Not Found" (or its
localized equivalent); anything else means the check failed. Remove each link alone, never
recursively (`rm <link>`, no `-r`; a junction with `cmd //c rmdir "$(cygpath -w <link>)"`, no
`/S`), check again, then `git worktree remove <dir>`, never `--force`. If a check fails, a link
stays or git refuses, leave the worktree and report it with why (implementer: under Risks;
reviewer: in `Checkout untouched`). Delete only paths you created in this dispatch; never delete
recursively through a link.
