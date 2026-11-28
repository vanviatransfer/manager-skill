# `explore`

Read by the code-map skill when using `explore`. No hook runs it and it adds nothing to the map;
the implementer brief points to it as the way to locate code before reading it.

**`<cmd> explore <name>... [--budget <chars>]`**. The source of named definitions, with their
callers. A `<name>` is taken as `calls` takes it: a bare name (`scan`), or one qualified by its
module or class (`codemap.scan`, `Box.size`, `outer.inner`). It matches definitions exactly (the
last part equal, the qualifier matching the end of the dotted name), never as a substring.

It is live, like `query` and `calls`: every run reads the working tree's files (the files the map
scans, with the same exclusions; files that may hold secrets are never read), reuses the `calls`
parse and resolution, and writes nothing. No page, index or `.codemap.json` changes.

## Using it

Run it before reading a function or class. The source it prints is the file as it is now (its
last line says so), so do not Read that range again unless you will edit it; before an Edit,
a ranged Read (`offset` and `limit`) of just that range is enough. Do not re-read a file that
has not changed.

## What it prints

Per name, `explore <name>: <n> definitions in <k> files`, then per definition (sorted by path,
then line):
- a header `path:start-end <kind> <name>`;
- the line-numbered source of exactly that range: `<number><tab><line>`, the `cat -n` and Read
  tool format, the numbers padded to the widest of the range.

Ranges:
- **Python**: from `ast` of the running Python, from the first decorator line through
  `end_lineno`, with lines counted as `ast` counts them (`\r\n`, a lone `\r` or `\n`). Kinds:
  `function`, `method`, `class`, with `async` when it is one. Nested definitions are found too
  (`outer.inner`, `Box.size`), and every definition of one name is printed: `@overload` stubs and
  the implementation, a property's getter and setter, a `def` in each branch of an `if`.
- **Other languages the map lists symbols for** (JavaScript, TypeScript, Go, Java, Kotlin, C#,
  Rust, PHP, Ruby, Swift, Scala) and **Python files that do not parse**: the map's line-pattern
  symbols; the range runs from the definition line to the line before the next symbol at the same
  or lower indentation, or the end of the file, trailing blank lines left out, at most 300 lines.
  The header says `(end approximate)` (and `not parsed: <why>`). No end within 300 lines: the
  header adds `end not found within 300 lines`, its range ends at the 300th line, and the source
  is followed by `end not found within 300 lines: read <path> from line <n>` (or the pointer
  below says `read <path> from line <n>; end not found within 300 lines`). Only the symbols the
  map lists count, so a range may hold other code after the definition ends.
  Kind: the keyword on the definition line (`class`, `interface`, `const`, ...; `def`, `fn`,
  `func` print as `function`).

A definition larger than the budget left:
- a class: its signature lines, then its members, each `  start-end <kind> <name>` (every
  member node once, two of one name included; at most 40, then a count), then `body not shown:
  read path:a-b`;
- anything else, or a class whose member list does not fit: its first lines (the whole
  signature, or none when the signature does not fit), then `body not shown: read path:a-b` for
  the lines not shown.

A name defined in more than 3 files prints headers only, no source, and says so on its first
line: qualify the name, or read one range.

Then, once per name:
- Python: `callers:` with the confident callers `calls` resolves, each `path:line in <symbol>`,
  at most 10, then `more: <k>; run calls <name>`; then `possible: <n> (calls <name> lists them)`.
  An empty list prints `callers: none resolved (not proof of none; run calls <name>)`. The
  callers are those of every matching definition; qualify the name for one. `calls.md` has what
  resolves and what doesn't.
- other languages: `callers: not resolved for <language>; grep -n -w <name>`; a Python file that
  does not parse: `callers: not resolved in Python files not parsed; grep -n -w <name>`.

A range past the end of the file is never printed unsaid: its header adds `(past the end of the
file: it has <n> lines)`.

Last, after any `cut:` lines:
- `not read: <k> tracked source files (secrets, vendored or skipped folders, too large or not
  text); grep them`, when any tracked Python or other symbol-listed source file was not read (as
  `calls` counts them), since a definition there can't be found;
- when any source was printed, `the source above is the working tree now: Read a range again
  only before an Edit of it`.

No exact match: `explore <name>: no definition named <name>; near matches:`, then at most 5
definitions whose names contain the last part of the name (any case), else close spellings, each
`path:line name` as `query` prints them, or `none found`. Nothing else, except, when source
files were not read, `(<k> tracked source files not read)` after the name on that line.

## Budget

`--budget <n>`: about `<n>` printed characters (default 8,000; characters, not the tokens of
`query --budget`). Headers, source, members, pointers and the callers lines count against it; the
callers lines are always printed, so they are taken out first. Not counted: the `over the
budget` line, the `cut:` lines, the `not read:` line and the closing line about the source. A
definition that doesn't fit, even in the short form above (at least its header and a pointer),
is cut, and every cut one is listed at the end, after `over the budget of <n> characters
(--budget):`, as `cut: path:a-b <kind> <name>` (at most 40, then one count line): never
silent. With nothing cut, neither line is printed.

## Limits

- Python ranges are exact for the working tree as the running Python parses it; other ranges are
  approximate and marked so.
- Callers are resolved for Python only, with every limit of `calls` (`calls.md`); for the rest,
  and before changing a signature, grep.
- Control characters other than a tab print as `?`.

Output is sorted by path, then line, so the same tree gives the same answer.
