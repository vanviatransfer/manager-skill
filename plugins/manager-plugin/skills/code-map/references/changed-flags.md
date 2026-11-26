# `changed`: possible weakened guards

Read by the code-map skill when `changed` prints its `possible weakened guards` section. The
section comes after the pointers (and after their 60-line cap), only when something is found;
without a finding the output is as before. Each line is `<kind>: <path>: <reason>`, sorted by kind
then path, at most 8, then `… <k> more` (9 are all shown: a more-line stands for two or more):
- `test file`: a test file (as `tests` counts them) deleted, renamed, moved, or moved and renamed
  (git's rename detection), and whether the new name is still a test's.
- `skip marker`: more lines with `@unittest.skip`, `skipTest(`, `pytest.mark.skip`,
  `pytest.mark.xfail`, `@Disabled` or `t.Skip(` than before; in a test file also `.only(`, `xit(`,
  `xdescribe(` and `.skip(`. Conditional skips don't count: `skipIf` / `skipUnless`,
  `pytest.mark.skipif`, and a skip call (`skipTest(`, `t.Skip(`, `.skip(`) after an `if` on its
  line or inside an `if`, `else`, `except`, `catch` or `case` block (the nearest line above with
  less indentation).
- `asserts`: a test file with fewer lines holding `assert` or the word `expect` than before. Only
  test code counts: a file under a test folder in a language the map parses, not its data files
  (JSON, YAML, text fixtures).
- `check config`: an edited, added or deleted lint, format, type-check, test or CI configuration
  (`.github/workflows/`, `.pre-commit-config*`, `setup.cfg`, `tox.ini`, `.flake8`, `mypy.ini`,
  `ruff.toml`, `.eslintrc*`, `tsconfig*.json`, `.golangci*`, ...), and a `pyproject.toml` whose
  `[tool.*]` tables differ.
- `suppression`: more lines with `noqa`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `nolint`
  or `pragma: no cover` than before; a `noqa` naming E402 (an import after a `sys.path` setup)
  doesn't count.

Counts compare the two versions of each file, so a moved line counts for nothing. Prose files
(`.md`, `.rst`, `.txt`, ...) and files that may hold secrets are not read. Approximate, never a
filter: a line is a reason to look at that part of the diff, not a verdict; a justified change
(a test moved with its code, a suppression with a stated reason) is fine. Known false positives:
splitting a test file into two gives `asserts` on the file the tests left (they moved, they
didn't go); a CI edit that only adds a job is still a `check config` line.
