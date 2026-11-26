#!/usr/bin/env python3
"""plan: check a living plan, and print the part of it one phase's work is read from.

Usage:
  plan.py check       exit 0 and `ok: <n> phases` if the plan is well formed, else 1 with one
                      `error:` line per problem; a `warning:` line never changes the exit code
  plan.py phase ID    print the section of phase ID with the constraints, the model-strategy
                      record, the binding decisions, the `## Phases` preamble and the open
                      owner decisions, in the plan's order; exit 1, with a line on standard
                      error, if the plan has no section for ID

The plan is read from standard input and neither command takes a path, so a phase is read from the
plan as a commit has it, never from a working tree:

  git show <base-sha>:<plan-path> | plan.py phase P3
  plan.py check < docs/LIVING_PLAN.md

The shape is the living-plan skill's template (`references/plan-template.md`). A line that starts
with `## ` opens a section and, under `## Phases`, one that starts with `### ` opens a phase,
wherever it stands (inside a code block too): the plan is split exactly as the `awk` command in
the manager's briefs splits it, so what `check` accepts is what both reads print.

phase prints the sections whose heading starts with `## Constraints`, `## Model strategy`,
`## Binding decisions` or `## Open owner decisions`, the lines from `## Phases` up to the first
`### ` heading, and every section whose heading starts with `### <ID>.`, each line as it is.

check reports as errors:
- no phase, or a `### ` heading under `## Phases` that is not `### <id>. <title>` (an id has no
  space and no dot);
- a phase id used twice;
- a phase without a `Status:`, `Objective:`, `Scope:`, `Depends on:`, `Risk:`, `Acceptance:` or
  `Validation:` line, or with nothing after one. A value starts after its label, which starts a
  line, and runs over the lines below it up to an empty line or a line that starts with one of
  these labels, `Notes:` or `Out of scope:` (any other `Word:` line is part of the value);
- a `Depends on` that names anything but phase ids (with commas, spaces or `and` between them;
  a remark in parentheses is skipped) or `none`;
- a dependency cycle.
And as a warning: two phases, neither done (a `Status` that starts with `done`) and neither
depending on the other (other phases between them included), whose `Scope` (up to an `Out of
scope`) names the same path. A path is a word with a `/` or a file extension; a folder and
something under it count as the same.
Also as warnings, one line per hit with the phase id and the field, after the ones above:
- a placeholder left in a required field: a template slot (`<` then `...` or a letter, up to the
  next `>`) outside backticks (inside them it is a command template, not flagged), and anywhere
  `TODO` or `TBD` as a word of its own (not part of a path such as `docs/TODO.md`), `???`,
  `NEEDS CLARIFICATION`;
- a `Validation` command piped into `tail`, `head`, `grep`, `less` or `tee`, which hides its exit
  code, unless the field names `pipefail` or `PIPESTATUS`.

Only the Python standard library is used (Python 3.8+). Nothing is written, executed or sent
anywhere. CRLF plans are accepted.
"""
import argparse
import re
import sys

PRINTED = ("## Constraints", "## Model strategy", "## Binding decisions",
           "## Open owner decisions")
REQUIRED = ("Status", "Objective", "Scope", "Depends on", "Risk", "Acceptance", "Validation")
HEADING = re.compile(r"### ([^\s.]+)\.(?:\s|$)")
LABEL = re.compile(r"(%s):(?:\s|$)" % "|".join(REQUIRED + ("Notes", "Out of scope")))
WORD = re.compile(r"[\w.~*/-]+")
EXTENSION = re.compile(r"\.[A-Za-z]\w+$")
SLOT = re.compile(r"<(?:\.\.\.|[A-Za-z])[^<>]*>")
PLACEHOLDER = re.compile(r"%s|(?<![\w/.-])(?:TODO|TBD)(?![\w/-]|\.\w)|\?\?\?|NEEDS CLARIFICATION"
                         % SLOT.pattern)
CODE = re.compile(r"`[^`]*`")
PIPED = re.compile(r"(?<!\|)\|(?![|&])\s*(tail|head|grep|less|tee)\b")


def phase(lines, wanted):
    """(the lines `phase` prints, whether a section of the wanted phase is among them)."""
    kept, found = [], False
    named = preamble = section = False
    for line in lines:
        if line.startswith("## "):
            named, preamble, section = line.startswith(PRINTED), line.startswith("## Phases"), False
        elif line.startswith("### "):
            preamble, section = False, line.startswith("### %s." % wanted)
            found = found or section
        if named or preamble or section:
            kept.append(line)
    return kept, found


def sections(lines):
    """[(heading, its line number, the lines below it)], one per `### ` heading under
    `## Phases`."""
    found, inside = [], False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.startswith("## Phases")
        elif inside and line.startswith("### "):
            found.append((line.strip(), number, []))
        elif inside and found:
            found[-1][2].append(line)
    return found


def fields(body):
    """{label: value} of a phase's `Label: value` lines; of a label used twice, the first."""
    values, name = {}, None
    for line in body:
        label = LABEL.match(line)
        if label:
            name = None if label.group(1) in values else label.group(1)
            if name:
                values[name] = line[label.end():].strip()
        elif not line.strip():
            name = None
        elif name:
            values[name] = (values[name] + " " + line.strip()).strip()
    return values


def depends(value):
    """The words a `Depends on` value names as phases; none for `none`."""
    words = re.split(r"[,\s]+", re.sub(r"\([^)]*\)", " ", value))
    words = [word.strip(".;") for word in words]
    words = [word for word in words if word and word != "and"]
    return [] if [word.lower() for word in words] == ["none"] else words


def paths(scope):
    """The paths a `Scope` value names, without what follows an `Out of scope`."""
    found = set()
    for word in WORD.findall(re.split(r"(?i)\bout of scope\b", scope)[0]):
        path = word.rstrip("./")
        if path and ("/" in word or EXTENSION.search(path)):
            found.add(path)
    return found


def check(lines):
    """(errors, warnings, the number of phases) of a plan."""
    errors, warnings, found = [], [], {}
    headings = sections(lines)
    if not headings:
        errors.append("no phase: no `### <id>. <title>` heading under `## Phases`")
    for heading, number, body in headings:
        match = HEADING.match(heading)
        if not match:
            errors.append("line %d: `%s` is not `### <id>. <title>`" % (number, heading))
        elif match.group(1) in found:
            errors.append("line %d: phase %s is already at line %d"
                          % (number, match.group(1), found[match.group(1)][0]))
        else:
            found[match.group(1)] = (number, fields(body))

    reach = {}  # phase: the phases it depends on, at first directly
    for name, (_, values) in found.items():
        for label in REQUIRED:
            if not values.get(label):
                errors.append("%s: no `%s:` line, or nothing after it" % (name, label))
        named = depends(values.get("Depends on", ""))
        reach[name] = set(word for word in named if word in found)
        if len(reach[name]) < len(set(named)):
            errors.append("%s: no such phase in `Depends on`: %s"
                          % (name, ", ".join(word for word in named if word not in found)))
    grown = True
    while grown:  # then through other phases too
        grown = False
        for seen in reach.values():
            more = set().union(*[reach[name] for name in seen]) - seen
            if more:
                seen |= more
                grown = True
    circular = [name for name in found if name in reach[name]]
    if circular:
        errors.append("dependency cycle through %s" % ", ".join(circular))

    todo = [(name, paths(values.get("Scope", ""))) for name, (_, values) in found.items()
            if not values.get("Status", "").lower().startswith("done")]
    for index, (one, mine) in enumerate(todo):
        for other, theirs in todo[index + 1:]:
            if one in reach[other] or other in reach[one]:
                continue
            same = sorted({min(a, b, key=len) for a in mine for b in theirs
                           if a == b or a.startswith(b + "/") or b.startswith(a + "/")})
            if same:
                warnings.append("%s and %s name the same path in Scope and neither depends on "
                                "the other: %s" % (one, other, ", ".join(same)))
    for name, (_, values) in found.items():
        warnings.extend(leftovers(name, values))
    return errors, warnings, len(found)


def leftovers(name, values):
    """Warnings for a phase's placeholders left in its required fields and for a validation
    command whose exit code a pipe hides."""
    found = []
    for label in REQUIRED:
        value = values.get(label, "")
        quoted = [span.span() for span in CODE.finditer(value)]
        for hit in PLACEHOLDER.finditer(value):
            if SLOT.fullmatch(hit.group(0)) and any(a < hit.start() and hit.end() < b
                                                    for a, b in quoted):
                continue  # a command template such as `git show <sha>`
            found.append("%s: %s: placeholder left in: %s" % (name, label, hit.group(0)))
    value = values.get("Validation", "")
    if not re.search(r"pipefail|PIPESTATUS", value):
        for hit in PIPED.finditer(value):
            found.append("%s: Validation: `| %s` hides the exit code of the command before it "
                         "(no `set -o pipefail` or `PIPESTATUS`)" % (name, hit.group(1)))
    return found


def write(stream, lines):
    """Bytes in, the same bytes out: a plan line is printed as it was read."""
    stream.buffer.write("".join(line + "\n" for line in lines).encode("utf-8", "surrogateescape"))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="plan.py", description="Check a living plan, or print the part of it one phase's "
                                    "work is read from. The plan is read from standard input.")
    commands = ap.add_subparsers(dest="command", metavar="check | phase ID", required=True)
    commands.add_parser("check", help="exit 0 if the plan is well formed, else 1 with one "
                                      "`error:` line per problem")
    commands.add_parser("phase", help="print one phase's section with the plan's constraints, "
                                      "decisions and model-strategy record"
                        ).add_argument("id", metavar="ID", help="the phase's id, e.g. P3")
    args = ap.parse_args(argv)
    lines = sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\n")
    if not lines[-1]:
        lines.pop()
    if args.command == "phase":
        kept, found = phase(lines, args.id)
        write(sys.stdout, kept)
        if not found:
            write(sys.stderr, ["plan.py: no `### %s.` section in the plan on standard input"
                               % args.id])
        return 0 if found else 1
    errors, warnings, count = check(lines)
    report = ["error: " + text for text in errors] + ["warning: " + text for text in warnings]
    if not errors:
        report.append("ok: %d phase%s" % (count, "" if count == 1 else "s"))
    write(sys.stdout, report)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
