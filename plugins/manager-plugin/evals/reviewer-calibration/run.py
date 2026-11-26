#!/usr/bin/env python3
"""run: start the reviewer-calibration eval (paid), then score it with score.py.

Usage:
  run.py --max-cost-usd USD [--tier base|hard] [--model sonnet|opus] [--runs N] [-j N]
         [--case GLOB] [--trust-plugin] [--dry-run]

Runs `claude plugin eval` on this plugin for the cases of one tier only: `--tier base` (the
default) takes the 20 cases tagged `reviewer-calibration`, `--tier hard` the 12 harder ones
tagged `reviewer-calibration-hard` (the CLI matches a tag exactly, so neither takes the other),
with the plugin on (`--ablation none`), each case's scaffold, no published report and the tools
the cases need (`Agent Bash ToolSearch`). Every run is a paid session: the cost ceiling is
required and passed as `--max-cost-usd` (the runner stops launching runs once it is reached,
exit 2, and reports what it has). Defaults: `--model sonnet` (the reviewer inherits the
session's model; `opus` for the stronger tier), `--runs 1`, `-j 1`. The result goes to
`evals-results/<UTC time>/` at the repository root (git ignores it), outside the plugin folder
that a run's session can read, so a later run finds no earlier trace there; score.py then reads
its `aggregate-result.json`. The eval's graders check the dispatch, the relayed answer and
blindness, not the verdict, which only score.py grades. run.py exits non-zero when the eval or
score.py does (score.py: 1 when a run is invalid). The eval asks to trust the plugin folder only
in an interactive terminal; without one it exits with an error, so pass `--trust-plugin` (handed
on to the eval) when you run it from a session or a script.

Traces: the eval removes each run's sandbox (`claude-eval-XXXXXX`, its `out/trace.jsonl`
included) when the run ends, unless `--keep-temp` is given, so run.py passes it. After the eval,
run.py copies each run's trace to `traces/<case>-<n>.jsonl` in the result folder, points the
result's `tracePath` there (the original path is kept as `keptTracePath`), and removes the kept
sandbox roots, only those the result names (the folder above `out/`, named `claude-eval-*` or
`e-*`), never by glob and without running anything inside them.

Before it launches, run.py refuses (exit 2) when the repository's path or the temp folder's
path holds a string the blind grader looks for, since every honest run would then fail it, and
warns when the repository is not under `$HOME`: the eval's Bash sandbox keeps the home folder
unreadable, so a checkout elsewhere (outside home and the temp folder) may leave the answer keys
readable to the session. On Windows it refuses to launch (exit 2): Claude Code has no Bash
sandbox there (CLI 2.1.330 refuses a session with Bash before it starts, and folder modes do not
restrict reads), so use Linux, macOS or a WSL2 distribution such as Ubuntu. `--dry-run` runs
these checks, prints both commands and runs nothing.
Standard library only.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(os.path.dirname(PLUGIN))
MODELS = ("sonnet", "opus")
TIER_TAGS = {"base": "reviewer-calibration", "hard": "reviewer-calibration-hard"}
SANDBOX_PREFIXES = ("claude-eval-", "e-")
TOOLS = ("Agent", "Bash", "ToolSearch")


def positive(kind):
    def read(text):
        try:
            value = kind(text)
        except ValueError:
            raise argparse.ArgumentTypeError("not a number: %s" % text)
        if value <= 0:
            raise argparse.ArgumentTypeError("must be above 0: %s" % text)
        return value
    return read


def parser():
    found = argparse.ArgumentParser(prog="run.py", description=__doc__.split("\n\n")[0])
    found.add_argument("--max-cost-usd", type=positive(float), required=True,
                       help="hard cost ceiling of the whole run, in USD (required)")
    found.add_argument("--tier", choices=sorted(TIER_TAGS), default="base",
                       help="the cases to run: base (20, the default) or hard (12)")
    found.add_argument("--model", choices=MODELS, default="sonnet")
    found.add_argument("--runs", type=positive(int), default=1)
    found.add_argument("-j", "--concurrency", type=positive(int), default=1)
    found.add_argument("--case", help="only the cases whose name matches this glob")
    found.add_argument("--trust-plugin", action="store_true",
                       help="pass --trust-plugin to the eval (needed without a terminal)")
    found.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    return found


def commands(args, stamp):
    """(the eval command, the score command) as argument lists."""
    out = os.path.join(REPO, "evals-results", stamp)
    if not 1 <= args.concurrency <= 8 or args.runs > 50:
        raise SystemExit("run.py: -j is 1-8 and --runs at most 50")
    run = ["claude", "plugin", "eval", PLUGIN, "--tag", TIER_TAGS[args.tier],
           "--ablation", "none", "--scaffold", "--no-publish", "--keep-temp",
           "--allow-tools"] + list(TOOLS) + [
           "--model", args.model, "--runs", str(args.runs), "-j", str(args.concurrency),
           "--max-cost-usd", "%g" % args.max_cost_usd, "--output-dir", out]
    if args.case:
        run += ["--case", args.case]
    if args.trust_plugin:
        run.append("--trust-plugin")
    score = [sys.executable, os.path.join(HERE, "score.py"),
             os.path.join(out, "aggregate-result.json")]
    return run, score


def blind_pattern():
    """The blind grader's pattern, from the first case's `graders/blind.md`."""
    for name in sorted(os.listdir(HERE)):
        path = os.path.join(HERE, name, "graders", "blind.md")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                return re.compile(fh.read().split("---")[-1].strip())
    raise SystemExit("run.py: no case with a blind grader in %s" % HERE)


def is_under(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def preflight(repo, temp, home):
    """(errors, warnings) about where the run would happen."""
    errors, warnings, blind = [], [], blind_pattern()
    for label, path in (("the repository path", repo), ("the temp folder (TMPDIR)", temp)):
        found = blind.search(path or "")
        if found:
            errors.append("%s %s holds %r, which the blind grader looks for in the trace: every "
                          "run would fail it. Move it (or set TMPDIR) elsewhere."
                          % (label, path, found.group(0)))
    if not home or not is_under(repo, home):
        warnings.append("the repository %s is not under $HOME (%s): the eval's Bash sandbox "
                        "hides the home folder, not this checkout, so the session may be able "
                        "to read the answer keys in evals-keys/ (read statically from the "
                        "2.1.332 sandbox builder)." % (repo, home or "unset"))
    return errors, warnings


def remove_tree(root):
    """Remove a kept sandbox root: its folders and files are opened to the owner first (the eval
    may have closed their modes, and git writes its objects read-only, which Windows will not
    delete); symbolic links are removed, never followed."""
    for top, dirs, files in os.walk(root):
        for name in dirs:
            path = os.path.join(top, name)
            if not os.path.islink(path):
                os.chmod(path, stat.S_IRWXU)
        for name in files:
            path = os.path.join(top, name)
            if not os.path.islink(path):
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    os.chmod(root, stat.S_IRWXU)
    shutil.rmtree(root)


def sandbox_root(trace):
    """The kept sandbox root that holds a trace (`<root>/out/trace.jsonl`), or None."""
    out = os.path.dirname(os.path.abspath(trace))
    root = os.path.dirname(out)
    if (os.path.basename(out) == "out" and os.path.basename(root).startswith(SANDBOX_PREFIXES)
            and os.path.isdir(root) and not os.path.islink(root)):
        return root
    return None


def collect(result):
    """Copy each run's trace beside `result`, point the result at the copies, then remove the
    sandbox roots it named. Returns the roots removed."""
    folder = os.path.dirname(os.path.abspath(result))
    with open(result, encoding="utf-8") as fh:
        data = json.load(fh)
    roots = []
    for case in data.get("cases", []):
        for number, run in enumerate((case.get("arms") or {}).get("with") or [], 1):
            trace = run.get("tracePath")
            if not trace or not os.path.isabs(trace) or not os.path.isfile(trace):
                continue
            copy = "traces/%s-%d.jsonl" % (case.get("name"), number)
            os.makedirs(os.path.join(folder, "traces"), exist_ok=True)
            shutil.copyfile(trace, os.path.join(folder, copy))
            run["keptTracePath"], run["tracePath"] = trace, copy
            root = sandbox_root(trace)
            if root and root not in roots:
                roots.append(root)
    with open(result, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    for root in roots:
        try:
            remove_tree(root)
        except OSError as error:
            sys.stderr.write("run.py: could not remove %s (%s); remove it by hand, without "
                             "running git inside it\n" % (root, error))
    return roots


def main(argv):
    args = parser().parse_args(argv)
    run, score = commands(args, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    errors, warnings = preflight(REPO, os.environ.get("TMPDIR") or tempfile.gettempdir(),
                                 os.environ.get("HOME") or os.path.expanduser("~"))
    if sys.platform.startswith("win") and not args.dry_run:
        errors.append("Windows has no Bash sandbox for the eval's session, so every run fails "
                      "before it starts; run it on Linux, macOS or a WSL2 distribution such as "
                      "Ubuntu.")
    for line in warnings:
        sys.stderr.write("run.py: warning: %s\n" % line)
    for line in errors:
        sys.stderr.write("run.py: refused: %s\n" % line)
    if errors:
        return 2
    if args.dry_run:
        print(" ".join(shlex.quote(part) for part in run))
        print(" ".join(shlex.quote(part) for part in score))
        return 0
    code = subprocess.call(run)
    if not os.path.isfile(score[-1]):
        sys.stderr.write("run.py: no %s (eval exit %d)\n" % (score[-1], code))
        return code or 1
    sys.stderr.write("run.py: eval exit %d (1: a case scored below 1, 2: the cost ceiling was "
                     "hit; the result holds what ran)\n" % code)
    collect(score[-1])
    scored = subprocess.call(score)
    return scored or code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
