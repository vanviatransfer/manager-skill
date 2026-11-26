# `changed`: possible weakened guards

Read by the code-map skill when `changed` prints its `possible weakened guards` section. The
section comes after the pointers (and after their 60-line cap), only when something is found;
without a finding the output is as before. Each line is `<kind>: <path>: <reason>`, sorted by kind
then path, at most 8, then `… <k> more`:
- `test file`: a test file (as `tests` counts them) deleted, renamed, moved, or moved and renamed
  (git's rename detection), and whether the new name is still a test's.
- `skip marker`: more lines with `@unittest.skip`, `skipTest(`, `pytest.mark.skip`,
  `pytest.mark.xfail`, `@Disabled` or `t.Skip(` than before; in a test file also `.only(`, `xit(`,
  `xdescribe(` and `.skip(`.
- `asserts`: a test file with fewer lines holding `assert` or the word `expect` than before.
- `check config`: an edited, added or deleted lint, format, type-check, test or CI configuration
  (`.github/workflows/`, `.pre-commit-config*`, `setup.cfg`, `tox.ini`, `.flake8`, `mypy.ini`,
  `ruff.toml`, `.eslintrc*`, `tsconfig*.json`, `.golangci*`, ...), and a `pyproject.toml` whose
  `[tool.*]` tables differ.
- `suppression`: more lines with `noqa`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `nolint`
  or `pragma: no cover` than before.

Counts compare the two versions of each file, so a moved line counts for nothing. Prose files
(`.md`, `.rst`, `.txt`, ...) and files that may hold secrets are not read. Approximate, never a
filter: a line is a reason to look at that part of the diff, not a verdict; a justified change
(a test moved with its code, a suppression with a stated reason) is fine.
