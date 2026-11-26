#!/usr/bin/env python3
"""score: grade the reviewer-calibration cases from a run, blind and deterministic.

Usage:
  score.py RESULT [--json]

RESULT is the `aggregate-result.json` that `claude plugin eval` writes (`run.py` names it), or a
folder of answer files `<case>.txt` / `<case>.<run>.txt` holding a reviewer's answer each (for
answers collected by hand). From a run's result, each run's answer is read from its trace (the
result's `tracePath`): the text the `manager-plugin:reviewer` agent returned to the orchestrator,
else the run's final message. The answer keys (`<case>/answer.json` beside this script) are read
here only; the reviewer never sees them.

Rules, per run of a case:
- The answer's `VERDICT:` line and its `Blockers:` entries (`B<n>.` up to the next section) are
  parsed; markdown emphasis and code fences around them are ignored. No verdict line: `no verdict`.
- planted: `found` when a blocker names one of the key's files (its path or file name) and either
  cites a line of that file inside the key's line range (`file:12` or `file:10-14`) or holds one
  of the key's terms (case-insensitive); otherwise `missed`. Other blockers are counted as extra.
- decoy, clean: any blocker, or a CHANGES REQUIRED verdict, is a `false alarm`; else `pass`.
  A run without a verdict counts against recall but is left out of the false-alarm rate.
- round2-fixed: `accepted` (right) with a PASS verdict and no blocker, else `rejected` (wrong).
- round2-unfixed: `rejected` (right) with a CHANGES REQUIRED verdict, else `accepted` (wrong);
  whether a blocker names the bug is shown as for a planted case.

Totals: recall per level (L1-L4, guard) and overall, the false-alarm rate (decoys and clean
diffs, apart and together), round-2 correctness, runs without a verdict, and per run the cost
(the result's `costUsd`) and tokens (input, cache read, cache write, output; summed over the
trace's assistant messages, each message id once; `reviewer` is the reviewer agent's share).
Exit 0 when it could score; 2 on a usage or input error. Standard library only, Python 3.8+.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = ("L1", "L2", "L3", "L4", "guard")
KINDS = ("planted", "decoy", "clean", "round2-fixed", "round2-unfixed")
REVIEWER = "manager-plugin:reviewer"
TOKEN_KEYS = (("input", "input_tokens"), ("cache read", "cache_read_input_tokens"),
              ("cache write", "cache_creation_input_tokens"), ("output", "output_tokens"))

VERDICT = re.compile(r"^[\s>*_`#]*VERDICT:[*_`\s]*(PASS WITH NOTES|PASS|CHANGES REQUIRED)\b",
                     re.M | re.I)
SECTION = re.compile(r"^[\s>*_`#-]*(Blockers|Notes|Acceptance|Validation|Not checked|"
                     r"Previous blockers|Checkout untouched|Reviewed SHA|Base SHA)\b[^:\n]*:",
                     re.I)
ENTRY = re.compile(r"^[\s>*_`#-]*B[0-9]+\s*[.):]", re.I)


def answer_keys(folder=HERE):
    """{case name: its answer.json} of every case folder beside this script."""
    keys = {}
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name, "answer.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                keys[name] = json.load(fh)
    return keys


def parse(text):
    """{"verdict": PASS | PASS WITH NOTES | CHANGES REQUIRED | None, "blockers": [entry text]}."""
    text = (text or "").replace("\r\n", "\n")
    match = VERDICT.search(text)
    verdict = match.group(1).upper() if match else None
    blockers, inside, current = [], False, None
    for line in text.split("\n"):
        section = SECTION.match(line)
        if section:
            if current is not None:
                blockers.append(current)
                current = None
            inside = section.group(1).lower() == "blockers"
            rest = line[section.end():].strip()
            if inside and rest and not re.match(r"[*_`(]*none\b", rest, re.I):
                current = rest
            continue
        if not inside:
            continue
        if ENTRY.match(line):
            if current is not None:
                blockers.append(current)
            current = line.strip()
        elif current is not None and line.strip() and not line.strip().startswith("```"):
            current += " " + line.strip()
    if current is not None:
        blockers.append(current)
    blockers = [b for b in blockers if not re.match(r"[*_`(]*none\b", b, re.I)]
    return {"verdict": verdict, "blockers": blockers}


def cites_lines(blocker, path, lines):
    """Whether the blocker cites `path:<n>` or `path:<a>-<b>` overlapping the key's range."""
    low, high = lines
    for name in {path, os.path.basename(path)}:
        for match in re.finditer(r"(?<![\w.-])" + re.escape(name) + r":(?:L)?([0-9]+)"
                                 r"(?:\s*[-–]\s*(?:L)?([0-9]+))?", blocker):
            start = int(match.group(1))
            end = int(match.group(2) or start)
            if start <= high and end >= low:
                return True
    return False


def names_file(blocker, path):
    return any(re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])", blocker)
               for name in {path, os.path.basename(path)})


def located(blocker, key):
    """Whether one blocker names the planted bug of the answer key."""
    lowered = blocker.lower()
    for place in key.get("locations", []):
        if not names_file(blocker, place["file"]):
            continue
        if cites_lines(blocker, place["file"], place["lines"]):
            return True
        if any(term.lower() in lowered for term in key.get("terms", [])):
            return True
    return False


def grade(key, text):
    """One run of a case: {"outcome", "right", "verdict", "blockers", "extra", "named"}."""
    review = parse(text)
    verdict, blockers = review["verdict"], review["blockers"]
    named = [b for b in blockers if located(b, key)]
    out = {"verdict": verdict, "blockers": len(blockers), "named": bool(named),
           "extra": len(blockers) - len(named)}
    kind = key["kind"]
    if verdict is None:
        out.update(outcome="no verdict", right=False)
    elif kind == "planted":
        out.update(outcome="found" if named else "missed", right=bool(named))
    elif kind in ("decoy", "clean"):
        alarm = bool(blockers) or verdict == "CHANGES REQUIRED"
        out.update(outcome="false alarm" if alarm else "pass", right=not alarm)
    elif kind == "round2-fixed":
        ok = verdict != "CHANGES REQUIRED" and not blockers
        out.update(outcome="accepted" if ok else "rejected", right=ok)
    elif kind == "round2-unfixed":
        ok = verdict == "CHANGES REQUIRED"
        out.update(outcome="rejected" if ok else "accepted", right=ok)
    else:
        raise ValueError("unknown kind %r" % kind)
    return out


def read_trace(path):
    events = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    return [event for event in events if isinstance(event, dict)]


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(part.get("text", part.get("content", "")))
                         for part in content if isinstance(part, dict))
    return ""


def from_trace(events):
    """(the reviewer's answer or the final message, {agent: {token field: n}})."""
    reviewers, answer, final = set(), None, None
    for event in events:
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        content = message.get("content") if isinstance(message.get("content"), list) else []
        for block in content:
            if not isinstance(block, dict):
                continue
            if (event.get("type") == "assistant" and block.get("type") == "tool_use"
                    and block.get("name") in ("Agent", "Task")
                    and (block.get("input") or {}).get("subagent_type") == REVIEWER):
                reviewers.add(block.get("id"))
            if (event.get("type") == "user" and block.get("type") == "tool_result"
                    and block.get("tool_use_id") in reviewers):
                answer = text_of(block.get("content"))
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            final = event["result"]
    tokens, seen = {"all": {}, "reviewer": {}}, set()
    for event in events:
        message = event.get("message")
        if event.get("type") != "assistant" or not isinstance(message, dict):
            continue
        usage = message.get("usage")
        ident = message.get("id")
        if not isinstance(usage, dict) or (ident and ident in seen):
            continue
        seen.add(ident)
        targets = ["all"] + (["reviewer"] if event.get("parent_tool_use_id") in reviewers
                             else [])
        for label, field in TOKEN_KEYS:
            value = usage.get(field)
            if isinstance(value, int):
                for target in targets:
                    tokens[target][label] = tokens[target].get(label, 0) + value
    return (answer if answer is not None and VERDICT.search(answer) else final or answer), tokens


def runs_from_result(path, keys):
    """[(case, run number, answer text, cost or None, tokens)] of an aggregate-result.json."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    base, runs = os.path.dirname(os.path.abspath(path)), []
    for case in data.get("cases", []):
        name = case.get("name")
        if name not in keys:
            continue
        for number, run in enumerate((case.get("arms") or {}).get("with") or [], 1):
            text, tokens = None, {"all": {}, "reviewer": {}}
            trace = run.get("tracePath")
            if trace:
                trace = trace if os.path.isabs(trace) else os.path.join(base, trace)
                if os.path.isfile(trace):
                    text, tokens = from_trace(read_trace(trace))
            runs.append((name, number, text, run.get("costUsd"), tokens))
    return runs


def runs_from_folder(folder, keys):
    runs = []
    for name in sorted(os.listdir(folder)):
        match = re.match(r"(.+?)(?:\.([0-9]+))?\.txt$", name)
        if match and match.group(1) in keys:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                runs.append((match.group(1), int(match.group(2) or 1), fh.read(), None,
                             {"all": {}, "reviewer": {}}))
    return runs


def ratio(part, whole):
    return "%d/%d" % (part, whole) + (" (%.0f%%)" % (100.0 * part / whole) if whole else "")


def report(runs, keys):
    """(the report's lines, its totals as a dict)."""
    lines, graded = ["case | run | kind | level | verdict | blockers | outcome | cost USD | "
                     "tokens all (in/cache read/cache write/out) | reviewer"], []
    for name, number, text, cost, tokens in sorted(runs, key=lambda r: (r[0], r[1])):
        key = keys[name]
        result = grade(key, text)
        graded.append((key, result, cost, tokens))
        lines.append(" | ".join([
            name, str(number), key["kind"], key.get("level") or "-", result["verdict"] or "none",
            str(result["blockers"]), result["outcome"] + (" (bug named)" if result["named"] and
                                                          key["kind"] == "round2-unfixed"
                                                          else ""),
            "%.2f" % cost if isinstance(cost, (int, float)) else "unknown",
            "/".join(str(tokens["all"].get(label, "?")) for label, _ in TOKEN_KEYS)
            if tokens["all"] else "unknown",
            "/".join(str(tokens["reviewer"].get(label, "?")) for label, _ in TOKEN_KEYS)
            if tokens["reviewer"] else "unknown"]))
    totals = {"runs": len(graded), "recall": {}, "no verdict": 0}
    planted = [(k, r) for k, r, _, _ in graded if k["kind"] == "planted"]
    for level in LEVELS:
        rows = [r for k, r in planted if k.get("level") == level]
        totals["recall"][level] = [sum(r["right"] for r in rows), len(rows)]
    totals["recall"]["all"] = [sum(r["right"] for _, r in planted), len(planted)]
    for kind in ("decoy", "clean"):
        rows = [r for k, r, _, _ in graded if k["kind"] == kind and r["verdict"] is not None]
        totals["false alarms " + kind] = [sum(not r["right"] for r in rows), len(rows)]
    totals["false alarms"] = [totals["false alarms decoy"][0] + totals["false alarms clean"][0],
                              totals["false alarms decoy"][1] + totals["false alarms clean"][1]]
    rows = [r for k, r, _, _ in graded if k["kind"].startswith("round2")]
    totals["round 2"] = [sum(r["right"] for r in rows), len(rows)]
    totals["no verdict"] = sum(r["verdict"] is None for _, r, _, _ in graded)
    costs = [c for _, _, c, _ in graded if isinstance(c, (int, float))]
    totals["cost USD"] = round(sum(costs), 4) if costs else None
    for agent in ("all", "reviewer"):
        summed = {}
        for _, _, _, tokens in graded:
            for label, value in tokens[agent].items():
                summed[label] = summed.get(label, 0) + value
        totals["tokens " + agent] = summed or None
    lines.append("")
    lines.append("recall: " + ", ".join("%s %s" % (level, ratio(*totals["recall"][level]))
                                        for level in LEVELS + ("all",)))
    lines.append("false alarms: decoys %s, clean %s, together %s" % (
        ratio(*totals["false alarms decoy"]), ratio(*totals["false alarms clean"]),
        ratio(*totals["false alarms"])))
    lines.append("round 2 right: %s" % ratio(*totals["round 2"]))
    lines.append("no verdict: %d of %d runs" % (totals["no verdict"], totals["runs"]))
    lines.append("cost USD: %s" % ("unknown" if totals["cost USD"] is None
                                   else "%.2f" % totals["cost USD"]))
    for agent in ("all", "reviewer"):
        summed = totals["tokens " + agent]
        lines.append("tokens %s: %s" % (agent, "unknown" if not summed else ", ".join(
            "%s %d" % (label, summed.get(label, 0)) for label, _ in TOKEN_KEYS)))
    return lines, totals


def main(argv):
    args = [a for a in argv if a != "--json"]
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write(__doc__.split("\n\n")[1] + "\n")
        return 2
    keys = answer_keys()
    try:
        if os.path.isdir(args[0]):
            runs = runs_from_folder(args[0], keys)
        else:
            runs = runs_from_result(args[0], keys)
    except (OSError, ValueError) as error:
        sys.stderr.write("score: can't read %s: %s\n" % (args[0], error))
        return 2
    if not runs:
        sys.stderr.write("score: no run of a reviewer-calibration case in %s\n" % args[0])
        return 2
    lines, totals = report(runs, keys)
    if "--json" in argv:
        print(json.dumps(totals, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
