# Where it writes: detection and map location

Read by the code-map skill when the layout is detected or changed (no `.codemap.json` yet,
`detect`, the first `build`, `build --redetect`), or when a `build` is refused over the layout.

Without `.codemap.json`, the script detects the vault, trying in order:
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
