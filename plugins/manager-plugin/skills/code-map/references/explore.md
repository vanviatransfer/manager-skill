# `explore`

Read by the code-map skill when using `explore`. No hook runs it and it adds nothing to the map;
the implementer brief points to it as the way to locate code before reading it.

**`<cmd> explore <name>... [--budget <chars>]`**. The source of named definitions, with their
callers. A `<name>` is taken as `calls` takes it: a bare name (`scan`), or one qualified by its
module or class (`codemap.scan`, `Box.size`, `outer.inner`). It matches definitions exactly (the
last part equal, the qualifier matching the end of the dotted name), never as a substring.

It is live, like `query` and `calls`: every run reads the working tree's files (the files the map
scans, with the same exclusions; files that may hold secrets are never read), reuses the `calls`
parse and resolution, and writes nothing. Only tracked files are searched: a new file counts once
it is `git add`ed. No page, index or `.codemap.json` changes.

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
  `end_lineno`, with lines counted as `ast` counts them (`\r\n`, a lone `\r` or `\n`; in a file
  with lone `\r` line breaks these numbers differ from the Read tool's, so its headers add
  `(lines counted as Python counts them; the Read tool sees this file differently)` and the
  closing line is the not byte-exact one). A file starting with a UTF-8 byte order mark is parsed
  without it (as `calls` does).
  Kinds: `function`, `method`, `class`, with `async` when it is one. Nested definitions are
  found too (`outer.inner`, `Box.size`), and every definition of one name is printed:
  `@overload` stubs and the implementation, a property's getter and setter, a `def` in each
  branch of an `if`.
- **Other languages the map lists symbols for** (JavaScript, TypeScript, Go, Java, Kotlin, C#,
  Rust, PHP, Ruby, Swift, Scala) and **Python files that do not parse**: the map's line-pattern
  symbols (for a Python file, its column-0 `def` and `class` only: its methods are not seen); the
  range runs from the definition line to the line before the next symbol at the same or lower
  indentation, or the end of the file, trailing blank lines left out, at most 300 lines.
  The header says `(end approximate)` (and `not parsed: <why>`). No end within 300 lines: the
  header adds `end not found within 300 lines`, its range ends at the 300th line, and the source
  is followed by `end not found within 300 lines: read <path> from line <n>` (or the pointer
  below says `read <path> from line <n>; end not found within 300 lines`). Only the symbols the
  map lists count, so a range may hold other code after the definition ends.
  Kind: the keyword on the definition line (`class`, `interface`, `const`, ...; `def`, `fn`,
  `func` print as `function`).
- **C and C++** (`cpp.md`): brace matching, skipping comments, strings and characters; exact
  when the file's braces balance, else the end is approximate as above, with `(end approximate:
  braces do not balance in this file)`. The header adds the Unreal tag (`[UFUNCTION
  BlueprintCallable]`) and, for a definition, `(declared <path>:<line>)`; a class's members add
  where an out-of-class definition is (`(defined <path>:a-b)`).

A definition larger than the budget left:
- a class: its signature lines (from its first line, its own decorators included, to the line
  before its body's first statement, or before that statement's first decorator when it has
  one), then its members, each `  start-end <kind> <name>` (every member node once, two of one
  name included, also those under `if`, `try` or `with` in the class body; at most 40, then a
  count), then `body not shown: read path:a-b`;
- anything else, or a class whose member list does not fit: its first lines (the whole
  signature, up to the line its body starts on when that line holds the signature's end too;
  or none when the signature does not fit), then `body not shown: read path:a-b` for
  the lines not shown.

A name defined in more than 3 files prints headers only, no source, and says so on its first
line: qualify the name, or read one range.

Then, once per name:
- Python: `callers:` with the confident callers `calls` resolves, each `path:line in <symbol>`,
  at most 10, then `more: <k>; run calls <name>`; then `possible: <n> (calls <name> lists them)`.
  An empty list prints `callers: none resolved (not proof of none; run calls <name>)`. The
  callers are those of every matching definition; qualify the name for one. `calls.md` has what
  resolves and what doesn't.
- C and C++: `callers: not resolved for C/C++; run calls <name> (text occurrences) or grep -n -w
  <name>`;
- other languages: `callers: not resolved for <language>; grep -n -w <name>`; a Python file that
  does not parse: `callers: not resolved in Python files not parsed; grep -n -w <name>`.

A range past the end of the file is never printed unsaid: its header adds `(past the end of the
file: it has <n> lines)`.

Last, after any `cut:` lines:
- `not read: <k> tracked source files (secrets, vendored or skipped folders, too large or not
  text); grep them`, when any tracked Python or other symbol-listed source file was not read (as
  `calls` counts them), since a definition there can't be found;
- `not parsed: <k> Python files not parsed (only their column-0 definitions searched): grep
  them`, when any Python file failed to parse;
- when any source was printed, `the source above is the working tree now: Read a range again
  only before an Edit of it`; when a printed range holds bytes that are not UTF-8 (shown as
  U+FFFD) or control characters (shown as `?`), instead `the source above is the working tree
  now, but not byte-exact (...): Read the range before an Edit of it`.

No exact match: `explore <name>: no definition named <name>; near matches:`, then at most 5
definitions whose names contain the last part of the name (any case), else close spellings, each
`path:line name` as `query` prints them, or `none found`. Nothing else, except notes in
parentheses after the name on that line, in this order: `<k> tracked source files not read`;
`<k> Python files not parsed (only their column-0 definitions searched): grep them`; `<languages>:
only mapped symbols searched; grep -n -w <name>` (for the languages found by line pattern, whose
map lists only some definitions, e.g. JavaScript and TypeScript exports); and `<k> files in
languages without symbols: grep them` (tracked files of a language the map lists no symbols for,
such as shell, SQL, Vue, Svelte, Dart, PowerShell, and `.pyi` stubs: never searched).

## Budget

`--budget <n>`: about `<n>` printed characters (default 8,000; characters, not the tokens of `query
--budget`). The `explore <name>:` head line, headers, source, members, pointers and the callers
lines count against it; the callers lines are always printed, so they are taken out first. Not
counted: the `over the budget` line, the `cut:` lines, the `not read:` and `not parsed:` lines and
the closing line about the source. A definition that doesn't fit, even in the short form above (at
least its header and a pointer), is cut, and every cut one is listed at the end, after `over the
budget of <n> characters (--budget):`, as `cut: path:a-b <kind> <name>` (at most 40, then one count
line: `cut: <k> more definitions of <name> in <path> not listed; read <path>, raise --budget or grep
-n -w <name>` when they are all one name in one file, else `cut: <k> more definitions not listed;
qualify the name or raise --budget`): never silent. With nothing cut, neither line is printed.

## Limits

- Python ranges are exact for the working tree as the running Python parses it, C and C++ ranges
  when the file's braces balance; other ranges are approximate and marked so.
- Callers are resolved for Python only (C and C++: text occurrences via `calls`), with every
  limit of `calls` (`calls.md`); for the rest, and before changing a signature, grep.
- Control characters other than a tab print as `?`.
- Output into a pipe that closes early (`explore x | head`) ends quietly with exit 0.

Output is sorted by path, then line, so the same tree gives the same answer.
