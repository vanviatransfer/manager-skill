#!/usr/bin/env python3
"""skilltrain: check and measure a project's self-training skills.

Usage:
  skilltrain.py check SKILL_DIR [--root DIR]   exit 0 if the skill (or trainer) is well formed,
                                               1 with one line per problem, 2 for a bad path
  skilltrain.py stats SKILL_DIR [--root DIR]   records, outcomes and tags since the last
                                               training, and whether training is due
  skilltrain.py due REPO_ROOT                  one line per marked skill under .claude/skills/:
                                               its training-due state, with its trainer if any

A worker skill is SKILL.md with the marker <!-- self-training-skill v1 --> right after its
frontmatter, lessons.md beside it, and the records file its "## Record" section names. A trainer
is SKILL.md with the marker <!-- self-training-trainer v1 --> whose "## Trains" section names one
worker. A SKILL.md without either marker is not checked.

SKILL_DIR is normally <repo>/.claude/skills/<name>; the repository root is then three folders up,
or --root gives it. Paths in the files are relative to the repository root.

Only the Python standard library is used (Python 3.8+). Nothing is executed and nothing is sent
anywhere. Nothing is read through a symlink (on Windows also a junction, with Python 3.12+).
CRLF files are accepted.
"""
import argparse
import os
import posixpath
import re
import sys

MARKER = "<!-- self-training-skill v1 -->"
TRAINER_MARKER = "<!-- self-training-trainer v1 -->"
MARKER_RE = re.compile(r"^<!-- self-training-(skill|trainer) v\d+ -->$")
SECTIONS = ("Purpose", "Steps", "Rules", "Knowledge", "Record", "Changelog")
TRAINER_SECTIONS = ("Trains", "Every use the owner reacts to", "Domain record fields",
                    "Next experiment", "Turning records into skill changes")
RECORDS_HEADER = ("date", "context", "outcome", "tags", "note")
LESSONS_HEADER = ("id", "lesson", "label", "evidence", "status")
OUTCOMES = ("pending-review", "pass", "changes-required", "owner-good", "owner-bad", "failed",
            "n/a")
BAD_OUTCOMES = {"changes-required", "owner-bad", "failed"}
OWNER_OUTCOMES = {"owner-good", "owner-bad"}
MAX_DESCRIPTION = 600
MAX_BODY_LINES = 200
MAX_BYTES = 4 * 1024 * 1024
DUE_RECORDS = 5
DUE_TAG_BAD = 2
TOP_TAGS = 10

DATE = r"\d{4}-\d{2}-\d{2}"
CHANGELOG_LINE = re.compile(r"^- v(\d+) (" + DATE + r"): \S")
LESSON_CITE = re.compile(r"\((L\d+(?:,\s*L\d+)*)\)\s*$")
OWNER_CITE = re.compile(r"\(owner: \".+\", " + DATE + r"\)\s*$")
PATH_LINE = re.compile(r"^(Skill|Records|Lessons):\s*`([^`]+)`")
CELL_SPLIT = re.compile(r"(?<!\\)\|")


class PathError(Exception):
    """A bad path: exit 2."""


def is_link(path):
    """A symlink, or on Windows a junction (Python 3.12+ can tell)."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def safe_rel(value):
    """A repository-relative posix path, or None if it points outside the repository."""
    value = value.replace("\\", "/").strip()
    norm = posixpath.normpath(value) if value else ""
    if not norm or norm == "." or norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or \
            norm == ".." or norm.startswith("../"):
        return None
    return norm


def link_in_path(root, rel):
    """True if the path or a folder on the way to it inside the repository is a symlink."""
    parts = rel.split("/")
    return any(is_link(os.path.join(root, *parts[:i])) for i in range(1, len(parts) + 1))


def read_rel(root, rel):
    """The text of a repository file (CRLF accepted). Raises ValueError with the reason."""
    if link_in_path(root, rel):
        raise ValueError("%s is, or lies under, a symlink; refused" % rel)
    full = os.path.join(root, *rel.split("/"))
    if not os.path.isfile(full):
        raise ValueError("%s does not exist" % rel)
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError("%s is larger than %d bytes" % (rel, MAX_BYTES))
    with open(full, "rb") as fh:
        data = fh.read()
    return data.replace(b"\r\n", b"\n").decode("utf-8", "replace")


def split_frontmatter(text):
    """(frontmatter dict or None, body lines)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            meta = {}
            for line in lines[1:i]:
                m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
                if m:
                    val = m.group(2).strip()
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                        val = val[1:-1]
                    meta[m.group(1)] = val
            body = lines[i + 1:]
            if body and body[-1] == "":
                body = body[:-1]
            return meta, body
    return None, lines


def marker_kind(body):
    """'skill', 'trainer' or None, from the first non-empty body line."""
    for line in body:
        if line.strip():
            m = MARKER_RE.match(line.strip())
            return m.group(1) if m else None
    return None


def sections(body):
    """[(title, [lines])] for the '## ' sections, in order."""
    out = []
    for line in body:
        if line.startswith("## "):
            out.append((line[3:].strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def section(secs, title):
    for name, lines in secs:
        if name == title:
            return lines
    return None


def check_order(secs, required, problems):
    names = [n for n, _ in secs]
    for title in required:
        if title not in names:
            problems.append("missing section: ## %s" % title)
    found = [n for n in names if n in required]
    if found != [t for t in required if t in found]:
        problems.append("sections out of order: %s (expected %s)"
                        % (", ".join(found), ", ".join(required)))


def cells(line):
    parts = CELL_SPLIT.split(line.strip())
    if len(parts) < 3 or parts[0].strip() or parts[-1].strip():
        return None
    return [p.strip() for p in parts[1:-1]]


def is_separator(line):
    row = cells(line)
    return bool(row) and all(re.match(r"^:?-{3,}:?$", c) for c in row)


def parse_table(text, header):
    """(header ok, rows as lists of len(header) cells). Rows follow the first table header."""
    lines = [ln for ln in text.split("\n")]
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        row = cells(line)
        ok = row is not None and tuple(c.lower() for c in row) == header and \
            i + 1 < len(lines) and is_separator(lines[i + 1])
        rows = []
        if ok:
            for rest in lines[i + 2:]:
                if not rest.strip().startswith("|"):
                    if rest.strip():
                        break
                    continue
                r = cells(rest)
                if r is None:
                    continue
                if len(r) > len(header):  # an unescaped pipe in the last cell
                    r = r[:len(header) - 1] + [" | ".join(r[len(header) - 1:])]
                rows.append(r + [""] * (len(header) - len(r)))
        return ok, rows
    return False, []


def bullets(lines):
    """Joined '- ' bullets of a section (continuation lines are indented)."""
    out = []
    for line in lines:
        if line.startswith("- "):
            out.append(line[2:].strip())
        elif out and line.startswith((" ", "\t")) and line.strip():
            out[-1] += " " + line.strip()
        elif not line.strip():
            continue
        else:
            out.append(None)  # a paragraph line ends the bullet
    return [b for b in out if b is not None]


def section_paths(lines):
    return {m.group(1): m.group(2) for m in (PATH_LINE.match(ln.strip()) for ln in lines) if m}


class Skill:
    def __init__(self, root, rel_dir):
        self.root = root
        self.rel_dir = rel_dir
        self.problems = []
        text = read_rel(root, rel_dir + "/SKILL.md")
        self.meta, self.body = split_frontmatter(text)
        self.kind = marker_kind(self.body)
        self.secs = sections(self.body)


def check_frontmatter(sk):
    if sk.meta is None:
        sk.problems.append("SKILL.md has no frontmatter")
        return
    for key in ("name", "description"):
        if not sk.meta.get(key):
            sk.problems.append("frontmatter lacks %s" % key)
    if len(sk.meta.get("description", "")) > MAX_DESCRIPTION:
        sk.problems.append("description is %d characters (at most %d)"
                           % (len(sk.meta["description"]), MAX_DESCRIPTION))


def records_rel(sk):
    lines = section(sk.secs, "Record") or []
    path = section_paths(lines).get("Records")
    if not path:
        sk.problems.append("## Record names no records path (a line `Records: `<path>``)")
        return None
    rel = safe_rel(path)
    if rel is None:
        sk.problems.append("records path is not inside the repository: %s" % path)
    return rel


def load_records(sk):
    rel = records_rel(sk)
    if rel is None:
        return None
    try:
        text = read_rel(sk.root, rel)
    except ValueError as exc:
        sk.problems.append("records: %s" % exc)
        return None
    ok, rows = parse_table(text, RECORDS_HEADER)
    if not ok:
        sk.problems.append("records: %s lacks the header | %s | and its separator"
                           % (rel, " | ".join(RECORDS_HEADER)))
        return None
    return rows


def load_lessons(sk):
    rel = sk.rel_dir + "/lessons.md"
    try:
        text = read_rel(sk.root, rel)
    except ValueError as exc:
        sk.problems.append("lessons: %s" % exc)
        return None
    ok, rows = parse_table(text, LESSONS_HEADER)
    if not ok:
        sk.problems.append("lessons: %s lacks the header | %s | and its separator"
                           % (rel, " | ".join(LESSONS_HEADER)))
        return None
    return {r[0]: r[4] for r in rows}


def changelog(sk):
    """[(version, date, text)] from ## Changelog; problems for bad lines."""
    out = []
    for line in section(sk.secs, "Changelog") or []:
        if not line.startswith("- "):
            continue
        m = CHANGELOG_LINE.match(line)
        if not m:
            sk.problems.append("changelog line doesn't match '- v<n> <YYYY-MM-DD>: ...': %s"
                               % line.strip())
            continue
        out.append((int(m.group(1)), m.group(2), line))
    return out


def check_worker(sk):
    check_frontmatter(sk)
    check_order(sk.secs, SECTIONS, sk.problems)
    if len(sk.body) > MAX_BODY_LINES:
        sk.problems.append("body is %d lines (at most %d)" % (len(sk.body), MAX_BODY_LINES))
    load_records(sk)
    lessons = load_lessons(sk)
    for b in bullets(section(sk.secs, "Rules") or []):
        m = LESSON_CITE.search(b)
        if m:
            for lid in re.split(r",\s*", m.group(1)):
                if lessons is None:
                    continue
                if lid not in lessons:
                    sk.problems.append("rule cites %s, which lessons.md lacks" % lid)
                elif lessons[lid].lower() == "retired":
                    sk.problems.append("rule cites %s, which is retired" % lid)
        elif not OWNER_CITE.search(b):
            sk.problems.append("rule cites no lesson or owner quote: %s" % b[:80])
    entries = changelog(sk)
    if section(sk.secs, "Changelog") is not None and not entries:
        sk.problems.append("changelog has no entry")
    for prev, cur in zip(entries, entries[1:]):
        if cur[0] <= prev[0]:
            sk.problems.append("changelog version v%d does not increase after v%d"
                               % (cur[0], prev[0]))


def worker_for_trainer(sk):
    """(worker rel dir, paths dict) from ## Trains, with problems recorded."""
    lines = section(sk.secs, "Trains") or []
    paths = section_paths(lines)
    name = paths.get("Skill")
    if not name:
        sk.problems.append("## Trains names no skill (a line `Skill: `<name>``)")
        return None, paths
    if "/" in name or "\\" in name or name in (".", ".."):
        sk.problems.append("## Trains skill must be a folder name: %s" % name)
        return None, paths
    return posixpath.join(posixpath.dirname(sk.rel_dir), name), paths


def check_trainer(sk):
    check_frontmatter(sk)
    check_order(sk.secs, TRAINER_SECTIONS, sk.problems)
    worker_dir, paths = worker_for_trainer(sk)
    if worker_dir:
        try:
            worker = Skill(sk.root, worker_dir)
            if worker.kind != "skill":
                sk.problems.append("trained skill %s is not a marked self-training skill"
                                   % worker_dir)
        except ValueError as exc:
            sk.problems.append("trained skill: %s" % exc)
    for key in ("Records", "Lessons"):
        path = paths.get(key)
        if not path:
            sk.problems.append("## Trains names no %s path (a line `%s: `<path>``)"
                               % (key.lower(), key))
            continue
        rel = safe_rel(path)
        if rel is None:
            sk.problems.append("%s path is not inside the repository: %s" % (key.lower(), path))
            continue
        try:
            read_rel(sk.root, rel)
        except ValueError as exc:
            sk.problems.append("%s: %s" % (key.lower(), exc))


def resolve(skill_dir, root_arg):
    """(root, skill rel dir). Raises PathError."""
    full = os.path.abspath(skill_dir)
    if root_arg:
        root = os.path.abspath(root_arg)
    else:
        parent = os.path.dirname(full)
        if os.path.basename(parent) != "skills" or \
                os.path.basename(os.path.dirname(parent)) != ".claude":
            raise PathError("%s is not <repo>/.claude/skills/<name>; give --root" % skill_dir)
        root = os.path.dirname(os.path.dirname(parent))
    try:
        rel = os.path.relpath(full, root).replace(os.sep, "/")
    except ValueError:
        raise PathError("%s is not inside %s" % (skill_dir, root))
    if safe_rel(rel) is None:
        raise PathError("%s is not inside %s" % (skill_dir, root))
    if link_in_path(root, rel):
        raise PathError("%s is, or lies under, a symlink; refused" % skill_dir)
    if not os.path.isfile(os.path.join(full, "SKILL.md")) or \
            is_link(os.path.join(full, "SKILL.md")):
        raise PathError("no SKILL.md (a plain file) in %s" % skill_dir)
    return root, rel


def load(root, rel):
    try:
        return Skill(root, rel)
    except ValueError as exc:
        raise PathError(str(exc))


def run_check(root, rel):
    sk = load(root, rel)
    if sk.kind is None:
        print("not a self-training skill")
        return 0
    (check_trainer if sk.kind == "trainer" else check_worker)(sk)
    for p in sk.problems:
        print("%s: %s" % (rel, p))
    if not sk.problems:
        print("ok: %s (%s)" % (rel, "trainer" if sk.kind == "trainer" else "skill"))
    return 1 if sk.problems else 0


def tags_of(row):
    return [t.strip().lower() for t in row[3].split(",") if t.strip()]


def measure(sk):
    """A dict of the numbers stats prints, or None with problems recorded."""
    rows = load_records(sk)
    entries = changelog(sk)
    if rows is None or not entries:
        if rows is not None:
            sk.problems.append("changelog has no entry")
        return None
    rows = [r for r in rows if any(r)]
    last_v, last_date, _ = entries[-1]
    since = [r for r in rows if re.match("^" + DATE + "$", r[0]) and r[0] >= last_date]
    outcomes = {}
    tags = {}
    bad_tags = {}
    for r in since:
        outcomes[r[2]] = outcomes.get(r[2], 0) + 1
        for t in tags_of(r):
            tags[t] = tags.get(t, 0) + 1
            if r[2] in BAD_OUTCOMES:
                bad_tags[t] = bad_tags.get(t, 0) + 1
    latest = {}
    for r in rows:
        latest[r[1]] = r[2]
    pending = sorted(c for c, o in latest.items() if o == "pending-review")
    all_tags = {t for r in rows for t in tags_of(r)}
    effects = []
    for v, date, line in entries:
        if date != last_date or "expect:" not in line:
            continue
        expect = line.split("expect:", 1)[1].split("— revert if:", 1)[0].lower()
        words = set(re.findall(r"[a-z0-9][a-z0-9_-]*", expect))
        dated = [r for r in rows if re.match("^" + DATE + "$", r[0])]
        before = [r for r in dated if r[0] < date]
        after = [r for r in dated if r[0] >= date]
        counts = [(t, sum(t in tags_of(r) for r in before), sum(t in tags_of(r) for r in after))
                  for t in sorted(all_tags & words)]
        effects.append((v, date, counts, len(before), len(after)))
    reasons = []
    if len(since) >= DUE_RECORDS:
        reasons.append("%d records since the last training" % len(since))
    for t in sorted(bad_tags):
        if bad_tags[t] >= DUE_TAG_BAD:
            reasons.append("tag %s %d times with a bad outcome" % (t, bad_tags[t]))
    return {
        "total": len(rows), "last": (last_v, last_date), "since": len(since),
        "outcomes": outcomes, "tags": tags, "pending": pending, "effects": effects,
        "owner_since": sum(1 for r in since if r[2] in OWNER_OUTCOMES),
        "owner_total": sum(1 for r in rows if r[2] in OWNER_OUTCOMES), "reasons": reasons,
    }


def run_stats(root, rel):
    sk = load(root, rel)
    if sk.kind != "skill":
        print("not a self-training skill" if sk.kind is None else
              "a trainer: run stats on the skill it trains")
        return 0
    m = measure(sk)
    if m is None:
        for p in sk.problems:
            print("%s: %s" % (rel, p))
        return 1
    print("skill: %s" % rel)
    print("records: %d" % m["total"])
    print("last training: v%d %s" % m["last"])
    print("records since (on or after %s): %d" % (m["last"][1], m["since"]))
    known = [o for o in OUTCOMES if o in m["outcomes"]] + \
        sorted(o for o in m["outcomes"] if o not in OUTCOMES)
    print("outcomes since: %s" % (", ".join("%s %d" % (o, m["outcomes"][o]) for o in known)
                                  or "none"))
    top = sorted(m["tags"].items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_TAGS]
    print("top tags since: %s" % (", ".join("%s %d" % kv for kv in top) or "none"))
    print("pending-review (resolve from git and GitHub): %s" % (", ".join(m["pending"]) or "none"))
    print("owner verdicts: %d since, %d in total" % (m["owner_since"], m["owner_total"]))
    for v, date, counts, nb, na in m["effects"]:
        detail = ", ".join("%s %d before, %d after" % c for c in counts) or "no known tags"
        print("expected effect v%d %s (records: %d before, %d after): %s"
              % (v, date, nb, na, detail))
    print("training due: %s" % ("yes (%s)" % "; ".join(m["reasons"]) if m["reasons"] else "no"))
    return 0


def run_due(root):
    base = ".claude/skills"
    folder = os.path.join(root, ".claude", "skills")
    if link_in_path(root, base):
        print("error: %s is, or lies under, a symlink; refused" % base, file=sys.stderr)
        return 2
    if not os.path.isdir(folder):
        print("no self-training skills")
        return 0
    workers, trainers = {}, {}
    for name in sorted(os.listdir(folder)):
        rel = base + "/" + name
        if not os.path.isfile(os.path.join(folder, name, "SKILL.md")):
            continue
        if link_in_path(root, rel + "/SKILL.md"):
            workers[name] = "refused: a symlink"
            continue
        try:
            sk = Skill(root, rel)
        except ValueError as exc:
            workers[name] = "error: %s" % exc
            continue
        if sk.kind == "trainer":
            worker_dir, _ = worker_for_trainer(sk)
            trainers.setdefault(posixpath.basename(worker_dir or ""), []).append(name)
        elif sk.kind == "skill":
            m = measure(sk)
            if m is None:
                workers[name] = "error: %s" % "; ".join(sk.problems)
            elif m["reasons"]:
                workers[name] = "training due (%s)" % "; ".join(m["reasons"])
            else:
                workers[name] = "not due (%d records since v%d)" % (m["since"], m["last"][0])
    if not workers and not trainers:
        print("no self-training skills")
    for name in sorted(workers):
        extra = trainers.pop(name, [])
        print("%s: %s%s" % (name, workers[name],
                            " [trainer: %s]" % ", ".join(extra) if extra else ""))
    for name in sorted(trainers):
        for t in trainers[name]:
            print("%s: trainer of %s, which is not a marked skill" % (t, name or "nothing"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skilltrain.py", description="Self-training skills.")
    ap.add_argument("action", choices=["check", "stats", "due"])
    ap.add_argument("path", help="check/stats: the skill folder; due: the repository root")
    ap.add_argument("--root", help="check/stats: the repository root (default: three folders up)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except AttributeError:
            pass
    try:
        if args.action == "due":
            root = os.path.abspath(args.path)
            if not os.path.isdir(root):
                raise PathError("no such directory: %s" % args.path)
            return run_due(root)
        root, rel = resolve(args.path, args.root)
        return (run_check if args.action == "check" else run_stats)(root, rel)
    except PathError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
