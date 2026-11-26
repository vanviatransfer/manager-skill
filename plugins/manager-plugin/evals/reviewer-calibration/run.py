#!/usr/bin/env python3
"""run: start the reviewer-calibration eval (paid), then score it with score.py.

Usage:
  run.py --max-cost-usd USD [--model sonnet|opus] [--runs N] [-j N] [--case GLOB] [--dry-run]

Runs `claude plugin eval` on this plugin for the cases tagged `reviewer-calibration` only, with
the plugin on (`--ablation none`), each case's scaffold, no published report and the tools the
cases need (`Agent Bash ToolSearch`). Every run is a paid session: the cost ceiling is required
and passed as `--max-cost-usd` (the runner stops launching runs once it is reached, exit 2, and
reports what it has). Defaults: `--model sonnet` (the reviewer inherits the session's model;
`opus` for the stronger tier), `--runs 1`, `-j 1`. The result goes to
`evals/results/reviewer-calibration-<UTC time>/` (git ignores it); score.py then reads its
`aggregate-result.json`, and run.py exits with score.py's code (the eval's exit code is printed:
a planted bug the reviewer misses fails that case's verdict grader). `--dry-run` prints both
commands and runs nothing. Standard library only.
"""
import argparse
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(HERE))
MODELS = ("sonnet", "opus")
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
    found.add_argument("--model", choices=MODELS, default="sonnet")
    found.add_argument("--runs", type=positive(int), default=1)
    found.add_argument("-j", "--concurrency", type=positive(int), default=1)
    found.add_argument("--case", help="only the cases whose name matches this glob")
    found.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    return found


def commands(args, stamp):
    """(the eval command, the score command) as argument lists."""
    out = os.path.join(PLUGIN, "evals", "results", "reviewer-calibration-" + stamp)
    if not 1 <= args.concurrency <= 8 or args.runs > 50:
        raise SystemExit("run.py: -j is 1-8 and --runs at most 50")
    run = ["claude", "plugin", "eval", PLUGIN, "--tag", "reviewer-calibration",
           "--ablation", "none", "--scaffold", "--no-publish", "--allow-tools"] + list(TOOLS) + [
           "--model", args.model, "--runs", str(args.runs), "-j", str(args.concurrency),
           "--max-cost-usd", "%g" % args.max_cost_usd, "--output-dir", out]
    if args.case:
        run += ["--case", args.case]
    score = [sys.executable, os.path.join(HERE, "score.py"),
             os.path.join(out, "aggregate-result.json")]
    return run, score


def main(argv):
    args = parser().parse_args(argv)
    run, score = commands(args, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
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
    return subprocess.call(score)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
