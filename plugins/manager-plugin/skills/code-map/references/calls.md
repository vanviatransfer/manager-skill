# `calls`

Read by the code-map skill when using `calls`. No hook runs it and it adds nothing to the map;
the reviewer brief asks for it (plus a grep) only for a function whose signature or behaviour
changed, when a `Code map` command is given.

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
  then `a.b.f()`, `from m import f`, `from pkg import m`), following re-exports (`from .core
  import f` in the file imported) up to 8 steps. Calls under another name count too, whatever
  its spelling, when it resolves to the definition: `from .core import f as g` re-exported and
  imported elsewhere, `from shim import h` of a `helper as h`, a module-level `alias =
  core.f` imported into another file.
- `possible:` every other occurrence of the name in the parsed Python code, each `path:line
  <kind>`: `call` (a bare call it can't resolve, e.g. after `from m import *` or from an import it
  can't resolve), `attribute call` (`x.name()` on an object of unknown type, `super().name()`,
  `Box().name()`), `reference` / `attribute reference` (passed or stored: `map(name, ...)`,
  `callbacks=[name]`), `renamed to X` (`X = name`, followed as a renamed name),
  `assignment` (rebound or patched), `decorator` (`@name` without a call;
  `@name(...)` is a call), `getattr` / `setattr` / `hasattr` / `delattr` with that literal,
  `import`, `other definition` (the same name defined elsewhere), and `string` (a string literal
  or docstring holding the word, any line of it). A use under another name says which:
  `call (alias h)`, `import (alias h)`; such a call it can't resolve is a `call (alias h)` here.
  Strings come after the code entries, each part by path and line.
- `text: <n> occurrences of <name>, <k> on lines listed above; grep the rest`: every whole-word
  occurrence of the bare name in every text file the map scans (any language, comments and
  Python files it couldn't parse included; the map's own pages left out), and how many of them
  are on lines printed above. When the function is bound to other names anywhere, the line adds
  `renamed: <names>` and ends `grep those too`; when the name is passed or stored (a `reference`
  or `attribute reference` above), it adds `passed or stored at <k> places above, calls through
  them not followed`. It says `all on lines listed above` only when neither applies.
  Renamed names: `import ... as X` and `from ... import f as X` that resolve to the definition
  or import a name already found, `X = f` or `X = m.f` in any scope (at module level also when
  it can't resolve them), and, the other way, the name a binding of the asked name imports or
  assigns; repeated until no more are found.

Then, once: `not parsed: <path> (<why>)` for each Python file it couldn't parse (a syntax
error, including syntax newer than the running Python, or a file too large or not text), and
always, even when nothing was found, the `coverage:` line: static Python calls only; not seen:
dynamic calls (`getattr` with computed names, `exec`), other languages, untracked files and
others outside the map; calls through `from m import *`, imports it can't resolve and methods
on objects of unknown type are under `possible`; other names the function is bound to are under
`renamed`; before changing the function's signature or behaviour, also grep for the name and
those. An empty section prints `none found`. It never says a function has no callers: an empty
`callers:` means none was resolved, not that none exists.

**Cap.** Each section of a name shows at most 40 lines, then `… <k> more (rerun with --all)`.
The `text:`, `not parsed:` and `coverage:` lines are never cut. `--budget` is `query` only.

**Limits.** Name resolution is by name and import only, with no types:
- a method called on an instance (`obj.name()`) is never confident;
- a name bound inside a function (`fn = f`) is followed in its own file only, and `x.<alias>()`
  only for aliases bound at module level;
- other binding forms (tuple unpacking, `dict` or list entries, function return values) are not
  followed, so their calls are in neither list: the `text:` count and a grep are the check;
- a local variable or parameter that shadows the name is not seen, so a shadowed call may be
  listed as a caller;
- a module is found by the map's import rules (the same as for importers) only; `sys.path`
  changes and installed packages are not followed.

Output is sorted by path, then line, so the same tree gives the same answer.
