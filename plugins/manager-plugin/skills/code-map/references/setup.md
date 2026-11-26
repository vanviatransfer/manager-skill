# Setting it up in a repository, and the rules block

Read by the code-map skill when setting the map up in a repository, when writing **The rules
block** by hand, or when a rules block is outdated.

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

## The rules block

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
the skill, never a path to the script (that differs per machine). The begin marker carries the
template's version (`v2`); a block with a lower one is outdated, and so is one with none (plugin
0.8.2 and earlier) whose text differs from this template: run `rules-hint` again and commit the
change (a block with a higher version, from a newer plugin, is left as it is). An unversioned
block with this template's text counts as current; the next `rules-hint` run writes the
versioned marker. A `SessionStart` hook
(`codemap-rules-version.sh`) names an outdated block in one line of information (the exact
command, and that a manager run does this in its setup PR) when a session starts in
a repository whose `AGENTS.md` or `CLAUDE.md` holds one; it reads those two files
only, writes nothing, and stays silent everywhere else and on any error. Without Python, write
the same block by hand:

```
<!-- manager-plugin:code-map:begin v2 (managed by the code-map skill) -->
- Before searching the code or the vault, read the vault index and the code map (paths in
  `.codemap.json`) and use the `manager-plugin:code-map` skill's `query`, not broad grep/glob;
  without the Skill tool, run the exact `query` command the plugin's search hook prints.
- After changing source files or vault pages, rebuild the map with that skill's `build` (its
  git commit hook does it when installed).
- Instead of `general-purpose`, use `manager-plugin:worker` for work that changes files,
  `manager-plugin:researcher` for read-only research, `manager-plugin:reviewer` for a review.
<!-- manager-plugin:code-map:end -->
```
