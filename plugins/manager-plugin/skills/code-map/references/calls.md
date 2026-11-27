# `calls`

Read by the code-map skill when using `calls`. It runs only when asked: no hook, brief step or
skill step runs it by default.

**`<cmd> calls <name>...`** (`--all`: no cap). Who calls a Python function or method, before
changing its signature or behaviour. A `<name>` is a function or class name (`scan`), or one
qualified by its module or class (`codemap.scan`, `Box.size`, `pkg.mod.Box.size`); the
qualifier matches the end of the definition's dotted name (module path, then classes and
enclosing functions).

It is live: every run reads the working tree's files (the files the map scans, with the same
exclusions: untracked, skipped folders, files that may hold secrets), parses the Python files
with the standard library `ast` of the Python running it, and writes nothing. No page, index or
`.codemap.json` changes.

Per name, in this order (`calls <name>` first):
- `definitions:` each `path:line qualified.name` that matches.
- `callers:` call sites resolved with confidence, each `path:line in <enclosing symbol>`
  (`(module level)` outside any): a call by the bare name in the defining file or an enclosing
  function; `self.<name>()` or `cls.<name>()` in the defining class; `Class.<name>()`; and calls
  through an import that resolves to the defining file (`import m` then `m.f()`, `import a.b`
  then `a.b.f()`, `from m import f`, `from pkg import m`, with `as` aliases), following
  re-exports (`from .core import f` in the file imported) up to 8 steps.
- `possible:` every other occurrence of the name in the parsed Python code, each `path:line
  <kind>`: `call` (a bare call it can't resolve, e.g. after `from m import *` or from an import it
  can't resolve), `attribute call` (`x.name()` on an object of unknown type, `super().name()`,
  `Box().name()`), `reference` / `attribute reference` (passed or stored: `map(name, ...)`,
  `callbacks=[name]`), `assignment` (rebound or patched), `decorator` (`@name` without a call;
  `@name(...)` is a call), `getattr` / `setattr` / `hasattr` / `delattr` with that literal,
  `import`, `other definition` (the same name defined elsewhere), and `string` (a string literal
  or docstring holding the word, any line of it). A use of an imported alias of the name says so:
  `call (alias h)`. Strings come after the code entries, each part by path and line.
- `text: <n> occurrences of <name>, <k> on lines listed above; grep the rest`: every whole-word
  occurrence of the bare name in every text file the map scans (any language, comments and
  Python files it couldn't parse included; the map's own pages left out), and how many of them
  are on lines printed above.

Then, once: `not parsed: <path> (<why>)` for each Python file it couldn't parse (a syntax
error, including syntax newer than the running Python, or a file too large or not text), and
always, even when nothing was found, the `coverage:` line: static Python calls only; not seen:
dynamic calls (`getattr` with computed names, `exec`), other languages, files outside the map;
aliases, `from m import *`, re-exports it can't follow and methods on objects of unknown type
are under `possible`; before changing the function's signature or behaviour, also grep for the
name. An empty section prints `none found`. It never says a function has no callers: an empty
`callers:` means none was resolved, not that none exists.

**Cap.** Each section of a name shows at most 40 lines, then `… <k> more (rerun with --all)`.
The `text:`, `not parsed:` and `coverage:` lines are never cut. `--budget` is `query` only.

**Limits.** Name resolution is by name and import only, with no types: a method called on an
instance (`obj.name()`) is never confident; a local variable or parameter that shadows the name
is not seen, so a shadowed call may be listed as a caller; a module found by the map's import
rules (the same as for importers) only; `sys.path` changes and installed packages are not
followed. Output is sorted by path, then line, so the same tree gives the same answer.
