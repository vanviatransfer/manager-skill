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

Run it before reading a function or class. The source it prints is the file as it is now, so do
not Read that range again unless you will edit it; before an Edit, a ranged Read (`offset` and
`limit`) of just that range is enough. Do not re-read a file that has not changed.

## What it prints

Per name, `explore <name>: <n> definitions in <k> files`, then per definition (sorted by path,
then line):
- a header `path:start-end <kind> <name>`;
- the line-numbered source of exactly that range: `<number><tab><line>`, the `cat -n` and Read
  tool format, the numbers padded to the widest of the range.

Ranges:
- **Python**: from `ast` of the running Python, from the first decorator line through
  `end_lineno`. Kinds: `function`, `method`, `class`, with `async` when it is one. Nested
  definitions are found too (`outer.inner`, `Box.size`).
- **Other languages the map lists symbols for** (JavaScript, TypeScript, Go, Java, Kotlin, C#,
  Rust, PHP, Ruby, Swift, Scala) and **Python files that do not parse**: the map's line-pattern
  symbols; the range runs from the definition line to the line before the next symbol at the same
  or lower indentation, or the end of the file, trailing blank lines left out, at most 300 lines.
  The header says `(end approximate)` (and `cut at 300 lines`, or `not parsed: <why>`). Only the
  symbols the map lists count, so a range may hold other code after the definition ends.
  Kind: the keyword on the definition line (`class`, `interface`, `const`, ...; `def`, `fn`,
  `func` print as `function`).

A definition larger than the budget left:
- a class: its signature lines, then its members, each `  start-end <kind> <name>` (at most 40,
  then a count), then `body not shown: read path:a-b`;
- anything else: its first lines (the signature at least), then `body not shown: read path:a-b`
  for the lines not shown.

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

No exact match: `explore <name>: no definition named <name>; near matches:`, then at most 5
definitions whose names contain the last part of the name (any case), else close spellings, each
`path:line name` as `query` prints them, or `none found`. Nothing else.

## Budget

`--budget <n>`: about `<n>` printed characters (default 8,000; characters, not the tokens of
`query --budget`). Headers, source, members, pointers and the callers lines count against it; the
callers lines are always printed, so they are taken out first. A definition that doesn't fit, even
in the short form above, is cut, and every cut one is listed at the end, after `over the budget of
<n> characters (--budget):`, as `cut: path:a-b <kind> <name>` (at most 40, then one count line):
never silent. With nothing cut, neither line is printed.

## Limits

- Python ranges are exact for the working tree as the running Python parses it; other ranges are
  approximate and marked so.
- Callers are resolved for Python only, with every limit of `calls` (`calls.md`); for the rest,
  and before changing a signature, grep.
- Control characters other than a tab print as `?`.

Output is sorted by path, then line, so the same tree gives the same answer.
