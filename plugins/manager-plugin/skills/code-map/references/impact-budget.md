# `impact` and `query --budget`

Read by the code-map skill when using `impact` or `query --budget`. Neither runs by default: no
hook, brief or skill step calls them.

**`<cmd> impact <path>...`** (or `impact --base <sha>`: the files changed since that commit,
compared with the working tree, as `mentions` takes them; `--depth <n>`, default 2). Per file the
map parses, compact and in a fixed order:
- `imported by`: the files that import it; `depth 2` and further: the files importing those, up
  to `--depth` levels, each file once. Import-based: local Python, JavaScript and TypeScript
  imports only (`imports: not parsed for <language>` otherwise).
- `tests`: the test files among those importers; `tests by name`: test files of its language
  named after it (`test_<name>`, `<name>_test`, ...) that don't import it.
- `referenced: <definition>: <files>`: per top-level definition (the first 20), the other source
  files of its language (JavaScript and TypeScript count as one, C and C++ too) whose text holds
  its name as a whole word, outside strings and comments for Python; its importers first.
  Name-based: anything else of the same name counts too, so it may include false matches; open
  the file before relying on one.
- Importer lists show 10 files, `referenced` lists 6, then `(+<k> more)`; at most 60 lines, then a
  count of the cut. Paths the map doesn't parse (another file type, a skipped or deleted file) are
  named on one line at the end. It writes nothing.

**`<cmd> query <term> --budget <n>`**: the same items as `query` (50 per section), ranked and
cut at about `<n>` tokens, estimated as characters / 4. Exact matches first (a definition named `<term>`, a path,
file name or file stem equal to it, a vault page with that name or title), then by how many files
import the file (for a definition, its file) or link to the page, then in `query`'s order. The
first item is always kept; an item that doesn't fit is skipped and later, smaller ones still go
in; a cut ends with `… <k> more (raise --budget)`. Sections keep their order (definitions, paths,
vault pages); one whose items were all cut is left out. Without `--budget`, `query` is
unchanged.
