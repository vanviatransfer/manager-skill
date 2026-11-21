#!/usr/bin/env python3
"""skilltrain: check and measure a project's self-training skills.

Usage:
  skilltrain.py check SKILL_DIR [--root DIR] [--triggers-from REF]
                                               exit 0 if the skill is well formed, 1 with one
                                               line per problem, 2 for a bad path (or a REF
                                               that isn't a commit, or no git)
  skilltrain.py stats SKILL_DIR [--root DIR]   records, outcomes and tags since the last
                                               training, and whether training is due
  skilltrain.py due REPO_ROOT                  one line per marked skill under .claude/skills/:
                                               its training-due state
  skilltrain.py query REPO_ROOT [--] TERM      one line per line of a marked skill's files
                                               holding TERM (case-insensitive): exit 0 with
                                               hits, 1 with none, 2 for a bad path or an empty
                                               TERM (`--` before a TERM starting with -)
  skilltrain.py rules-hint REPO_ROOT [--remove]
                                               the one-line instruction in CLAUDE.md (or where
                                               it already is): exit 0, 2 when refused

A worker skill is SKILL.md with the marker <!-- self-training-skill v1 --> right after its
frontmatter, lessons.md beside it, and the records file its "## Record" section names. A SKILL.md
with the old trainer marker <!-- self-training-trainer v1 --> is a retired trainer: check, stats
and due report it for deletion (exit 1 for check and stats). A SKILL.md without a marker is not
checked; one whose first body line is an HTML comment naming self-training, or with a marker
further down, is reported.

SKILL_DIR is normally <repo>/.claude/skills/<name>; the repository root is then three folders up,
or --root gives it. Paths in the files are relative to the repository root.

check also holds the skill's knowledge routing to its files: every file under the skill's
references/ needs a "## Knowledge" bullet that starts with its path in backticks
(`references/<file>` — read when ...), and every such bullet's path must exist (a path that
starts with references/ is in the skill's folder, any other is from the repository root;
backticked text with whitespace, ://, * or ?, or starting with <, is no path and not checked). Every
lesson id a rule cites must be in lessons.md. With --triggers-from REF, every quoted phrase
("..." or “...”) of the skill's description at REF, and of the description of the folder
<name>-trainer beside it at REF (the retired trainer), must still be in the current
description. A skill missing at REF is new: a note, not a problem; a trainer missing at REF is
skipped silently.

query and rules-hint read the marked skills the same way; query writes nothing, rules-hint
writes only CLAUDE.md or AGENTS.md.

"Since the last training" means the record rows after the count its last changelog entry gives
as `records: <n>`, or, for an entry without one, the rows dated strictly after its date.

Only the Python standard library is used (Python 3.8+). Nothing is executed but git (read-only,
for --triggers-from) and nothing is sent anywhere. Nothing is read through a symlink (on Windows
also a junction, with Python 3.12+). CRLF files are accepted.
"""
import argparse
import datetime
import os
import posixpath
import re
import subprocess
import sys

MARKER = "<!-- self-training-skill v1 -->"
MARKER_RE = re.compile(r"^<!-- self-training-(skill|trainer) v\d+ -->$")
SECTIONS = ("Purpose", "Steps", "Rules", "Knowledge", "Record", "Changelog")
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
# the "— records: <n>" segment (an em dash or " - " before it); the last one counts
CHANGELOG_RECORDS = re.compile(r"(?:—|\s-)\s*records:\s*(\d+)\b")
FENCE = re.compile(r"^\s*(```|~~~)")
BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
# Inside a bullet, only these start a sub-bullet (CommonMark: "3." can't interrupt a paragraph).
SUB_BULLET = re.compile(r"^(?:[-*+]|1[.)])\s+")
LESSON_CITE = re.compile(r"\((L\d+(?:,\s*L\d+)*)\)\s*$")
OWNER_CITE = re.compile(r"\(owner: \".+\", " + DATE + r"\)\s*$")
PATH_LINE = re.compile(r"^(Records):\s*`([^`]+)`")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
# A ## Knowledge routing: a bullet that starts with a path in backticks.
ROUTE = re.compile(r"^`([^`]+)`")
QUOTED = re.compile(r'"([^"\n]+)"|\u201c([^\u201d\n]+)\u201d')
MAX_HITS = 50
MAX_SNIPPET = 100
RULES_PREFIX = "<!-- manager-plugin:self-training-skills"
RULES_MARK = RULES_PREFIX + " -->"
# The marker of a CLAUDE.md rules-hint created: --remove deletes only such a file, and only when
# nothing but its title is left.
RULES_MARK_CREATED = RULES_PREFIX + "; it created this file -->"
RULES_TEXT = ("- before searching skill files use `skilltrain.py query`; after changing a skill "
              "run `skilltrain.py check`")
RULES_LINE = RULES_TEXT + " " + RULES_MARK
RULES_LINE_CREATED = RULES_TEXT + " " + RULES_MARK_CREATED
RULES_TITLE = "# Project instructions"


NEAR_MISS = ("the marker doesn't match: the line right after the frontmatter must be exactly %s"
             % MARKER)
RETIRED = ("retired trainer (self-training-skills 0.9.3 dropped trainers): delete this folder; "
           "its worker's Record section now holds its rules")


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
    text = data.replace(b"\r\n", b"\n").decode("utf-8", "replace")
    return text[1:] if text.startswith("\ufeff") else text  # a UTF-8 BOM


def split_frontmatter(text):
    """(frontmatter dict or None, body lines)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            meta = {}
            fm = lines[1:i]
            j = 0
            while j < len(fm):
                m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", fm[j])
                j += 1
                if not m:
                    continue
                val = m.group(2).strip()
                more = []
                while j < len(fm) and (fm[j].startswith((" ", "\t")) or not fm[j].strip()):
                    more.append(fm[j].strip())
                    j += 1
                while more and not more[-1]:
                    more.pop()
                if re.match(r"^[>|][+-]?$", val):  # a folded or literal block scalar
                    val = ("\n" if val[0] == "|" else " ").join(more)
                elif more:  # a plain scalar continued on indented lines
                    val = " ".join([val] + [ln for ln in more if ln])
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = unquote(val)
                meta[m.group(1)] = val
            body = lines[i + 1:]
            if body and body[-1] == "":
                body = body[:-1]
            return meta, body
    return None, lines


def unquote(val):
    """A YAML quoted scalar's text: \\" and \\\\ (and \\n, \\t) in double quotes, '' in single."""
    if val[0] == "'":
        return val[1:-1].replace("''", "'")
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)),
                  val[1:-1])


def marker_kind(body):
    """'skill', 'trainer' (retired), 'near-miss' or None, from the first non-empty body line.

    near-miss: that line is an HTML comment naming self-training without matching a marker, or
    a marker stands elsewhere in the body."""
    first = next((ln.strip() for ln in body if ln.strip()), "")
    m = MARKER_RE.match(first)
    if m:
        return m.group(1)
    if first.startswith("<!--") and "self-training" in first.lower():
        return "near-miss"
    if any(MARKER_RE.match(ln.strip()) for ln in body):
        return "near-miss"
    return None


def sections(body):
    """[(title, [lines])] for the '## ' sections, in order ('## ' inside a fenced code block
    doesn't count)."""
    out = []
    fence = None
    for line in body:
        f = FENCE.match(line)
        if f:
            fence = None if fence == f.group(1) else (fence or f.group(1))
        if fence is None and not f and line.startswith("## "):
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
    """(header ok, rows as lists of len(header) cells, their line numbers, line numbers of
    lines that don't parse as rows). Rows follow the first table header; blank lines are
    allowed. The table ends at the first other line: it and every later non-blank line are
    reported as rows that don't parse."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        row = cells(line)
        ok = row is not None and tuple(c.lower() for c in row) == header and \
            i + 1 < len(lines) and is_separator(lines[i + 1])
        rows, numbers, bad = [], [], []
        if ok:
            ended = False
            for n, rest in enumerate(lines[i + 2:], i + 3):
                if not rest.strip():
                    continue
                r = None if ended or not rest.strip().startswith("|") else cells(rest)
                if r is None or len(r) < len(header):
                    bad.append(n)
                    ended = ended or not rest.strip().startswith("|")
                    continue
                if len(r) > len(header):  # an unescaped pipe in the last cell
                    r = r[:len(header) - 1] + [" | ".join(r[len(header) - 1:])]
                rows.append(r)
                numbers.append(n)
        return ok, rows, numbers, bad
    return False, [], [], []


def bullets(lines):
    """(joined top-level bullets ('-', '*', '+' or numbered), paragraph lines that aren't in a
    bullet). Indented continuation lines join their bullet; indented sub-bullets, and the
    lines under them, belong to their parent and are skipped; fenced code is skipped."""
    out, stray = [], []
    in_sub = False
    fence = None
    for line in lines:
        f = FENCE.match(line)
        if f or fence:
            if f:
                fence = None if fence == f.group(1) else (fence or f.group(1))
            continue
        if not line.strip():
            continue
        m = BULLET.match(line)
        if m:
            out.append(line[m.end():].strip())
            in_sub = False
        elif out and line.startswith((" ", "\t")):
            if SUB_BULLET.match(line.strip()):
                in_sub = True
            if not in_sub:
                out[-1] += " " + line.strip()
        else:
            stray.append(line.strip())
    return out, stray


def section_paths(lines):
    return {m.group(1): m.group(2) for m in (PATH_LINE.match(ln.strip()) for ln in lines) if m}


class Skill:
    def __init__(self, root, rel_dir):
        self.root = root
        self.rel_dir = rel_dir
        self.problems = []
        self.skipped = []  # file:line of records lines that don't parse
        self.record_lines = []  # file:line of each parsed records row
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
    ok, rows, numbers, bad = parse_table(text, RECORDS_HEADER)
    if not ok:
        sk.problems.append("records: %s lacks the header | %s | and its separator"
                           % (rel, " | ".join(RECORDS_HEADER)))
        return None
    sk.skipped = ["%s:%d" % (rel, n) for n in bad]
    sk.record_lines = ["%s:%d" % (rel, n) for n in numbers]
    return rows


def load_lessons(sk):
    rel = sk.rel_dir + "/lessons.md"
    try:
        text = read_rel(sk.root, rel)
    except ValueError as exc:
        sk.problems.append("lessons: %s" % exc)
        return None
    ok, rows, _, bad = parse_table(text, LESSONS_HEADER)
    if not ok:
        sk.problems.append("lessons: %s lacks the header | %s | and its separator"
                           % (rel, " | ".join(LESSONS_HEADER)))
        return None
    for n in bad:
        sk.problems.append("lessons: %s:%d is a row that doesn't parse" % (rel, n))
    return {r[0]: r[4] for r in rows}


def changelog(sk):
    """[(version, date, text, records consumed or None)] from ## Changelog; problems for bad
    lines. Indented continuation lines are joined to their entry."""
    joined = []
    for line in section(sk.secs, "Changelog") or []:
        if line.startswith("- "):
            joined.append(line.rstrip())
        elif joined and line.startswith((" ", "\t")) and line.strip():
            joined[-1] += " " + line.strip()
        elif line.strip():
            sk.problems.append("changelog line is not a '- v<n> <YYYY-MM-DD>: ...' entry or an "
                               "indented continuation: %s" % line.strip()[:80])
    out = []
    for line in joined:
        m = CHANGELOG_LINE.match(line)
        if not m:
            sk.problems.append("changelog line doesn't match '- v<n> <YYYY-MM-DD>: ...': %s"
                               % line.strip()[:80])
            continue
        r = CHANGELOG_RECORDS.findall(line)
        out.append((int(m.group(1)), m.group(2), line, int(r[-1]) if r else None))
    return out


def valid_date(text):
    if not re.match("^" + DATE + "$", text):
        return False
    try:
        datetime.date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return False
    return True


def check_worker(sk):
    check_frontmatter(sk)
    check_order(sk.secs, SECTIONS, sk.problems)
    if len(sk.body) > MAX_BODY_LINES:
        sk.problems.append("body is %d lines (at most %d)" % (len(sk.body), MAX_BODY_LINES))
    rows = load_records(sk)
    for where in sk.skipped:
        sk.problems.append("records: %s is a row that doesn't parse" % where)
    for row, where in zip(rows or [], sk.record_lines):
        if not valid_date(row[0]):
            sk.problems.append("records: %s has a date that isn't YYYY-MM-DD: %s" % (where, row[0]))
        if row[2] not in OUTCOMES:
            sk.problems.append("records: %s has an unknown outcome: %s (one of %s)"
                               % (where, row[2], ", ".join(OUTCOMES)))
    lessons = load_lessons(sk)
    rules, stray = bullets(section(sk.secs, "Rules") or [])
    for line in stray:
        sk.problems.append("rule without a bullet/citation: %s" % line[:80])
    for b in rules:
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
    counts = [(e[0], e[3]) for e in entries if e[3] is not None]
    for (pv, pn), (cv, cn) in zip(counts, counts[1:]):
        if cn < pn:
            sk.problems.append("changelog v%d records: %d is less than v%d's %d" % (cv, cn, pv, pn))
    if rows is not None and counts and counts[-1][1] > len(rows):
        sk.problems.append("changelog v%d records: %d, but the records file has %d rows"
                           % (counts[-1][0], counts[-1][1], len(rows)))


def reference_files(sk):
    """The repository-relative paths of the plain files under the skill's references/ (dot
    files and symlinks left out)."""
    base = sk.rel_dir + "/references"
    top = os.path.join(sk.root, *base.split("/"))
    if link_in_path(sk.root, base) or not os.path.isdir(top):
        return []
    out = []
    for folder, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                         and not is_link(os.path.join(folder, d)))
        for f in sorted(files):
            if f.startswith(".") or is_link(os.path.join(folder, f)):
                continue
            rel = os.path.relpath(os.path.join(folder, f), sk.root).replace(os.sep, "/")
            out.append(rel)
    return out


def is_route(written):
    """False for backticked text that is no path: a URL, a command or anything with
    whitespace, a glob (* or ?), a <placeholder>."""
    return not ("://" in written or re.search(r"\s", written) or "*" in written or
                "?" in written or written.startswith("<"))


def routings(sk):
    """[(path as written, repository-relative path or None)] of the ## Knowledge bullets that
    start with a path in backticks. A path starting with references/ is in the skill's folder;
    any other is from the repository root; a #anchor is dropped."""
    items, _ = bullets(section(sk.secs, "Knowledge") or [])
    out = []
    for b in items:
        m = ROUTE.match(b)
        if not m:
            continue
        written = m.group(1).strip()
        if not is_route(written):
            continue
        path = written.split("#", 1)[0].strip()
        if path.startswith("./"):
            path = path[2:]
        if path.startswith("references/"):
            path = sk.rel_dir + "/" + path
        out.append((written, safe_rel(path) if path else None))
    return out


def check_routing(sk):
    routed = set()
    for written, rel in routings(sk):
        if rel is None:
            sk.problems.append("knowledge routing points outside the repository: %s" % written)
            continue
        routed.add(rel)
        if link_in_path(sk.root, rel):
            sk.problems.append("knowledge routing %s is, or lies under, a symlink" % written)
        elif not os.path.exists(os.path.join(sk.root, *rel.split("/"))):
            sk.problems.append("knowledge routing points at a missing file: %s" % written)
    prefix = sk.rel_dir + "/"
    for rel in reference_files(sk):
        if rel not in routed:
            short = rel[len(prefix):]
            sk.problems.append("%s has no routing in ## Knowledge (a bullet \"- `%s` — read "
                               "when ...\")" % (short, short))


def quoted(text):
    """The quoted phrases ("..." or \u201c...\u201d) of a text, whitespace collapsed."""
    out = []
    for a, b in QUOTED.findall(text or ""):
        phrase = " ".join((a or b).split())
        if phrase and phrase not in out:
            out.append(phrase)
    return out


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except OSError:
        raise PathError("--triggers-from needs git, and git can't be run")


def resolve_ref(root, ref):
    """The commit SHA of REF in the repository at root. Raises PathError."""
    if not ref or ref.startswith("-") or any(ord(c) < 32 for c in ref):
        raise PathError("--triggers-from: not a git ref: %r" % ref)
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        raise PathError("--triggers-from: %s is not in a git repository" % root)
    p = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    sha = p.stdout.decode("ascii", "replace").strip()
    if p.returncode != 0 or not sha:
        raise PathError("--triggers-from: no commit %s in %s (fetch it first?)" % (ref, root))
    return sha


def file_at(root, sha, rel):
    """The text of a plain file at a commit, or None when it isn't there (or is a symlink)."""
    p = git(root, "ls-tree", "-z", sha, "--", rel)
    entry = p.stdout.split(b"\0")[0] if p.returncode == 0 else b""
    if not entry.startswith((b"100644 blob ", b"100755 blob ")):
        return None
    p = git(root, "cat-file", "blob", "%s:./%s" % (sha, rel))
    if p.returncode != 0 or len(p.stdout) > MAX_BYTES:
        return None
    text = p.stdout.replace(b"\r\n", b"\n").decode("utf-8", "replace")
    return text[1:] if text.startswith("\ufeff") else text


def check_triggers(sk, ref, sha, notes):
    """Every quoted phrase of the skill's and its retired trainer's description at the commit
    must still be in the current description."""
    current = " ".join((sk.meta or {}).get("description", "").split())
    name = posixpath.basename(sk.rel_dir)
    parent = posixpath.dirname(sk.rel_dir)
    trainer = (parent + "/" if parent else "") + name + "-trainer"
    for source, rel in (("skill", sk.rel_dir), ("trainer", trainer)):
        text = file_at(sk.root, sha, rel + "/SKILL.md")
        if text is None:
            if source == "skill":
                notes.append("note: %s/SKILL.md is not in %s: a new skill, no triggers to keep"
                             % (rel, ref))
            continue
        meta = split_frontmatter(text)[0] or {}
        for phrase in quoted(meta.get("description")):
            if phrase not in current:
                sk.problems.append("description dropped the trigger \"%s\" (from the %s's "
                                   "description at %s: %s/SKILL.md)"
                                   % (phrase, source, ref, rel))


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


def run_check(root, rel, triggers_from=None):
    sha = resolve_ref(root, triggers_from) if triggers_from is not None else None
    sk = load(root, rel)
    if sk.kind is None:
        print("not a self-training skill")
        return 0
    notes = []
    if sk.kind == "near-miss":
        sk.problems.append(NEAR_MISS)
    elif sk.kind == "trainer":
        sk.problems.append(RETIRED)
    else:
        check_worker(sk)
        check_routing(sk)
        if sha:
            check_triggers(sk, triggers_from, sha, notes)
    for n in notes:
        print(n)
    for p in sk.problems:
        print("%s: %s" % (rel, p))
    if not sk.problems:
        print("ok: %s (skill)" % rel)
    return 1 if sk.problems else 0


def tags_of(row):
    return [t.strip().lower() for t in row[3].split(",") if t.strip()]


def split_at(rows, date, consumed):
    """(before, after) a changelog entry: by the rows it consumed, else strictly by date."""
    if consumed is not None:
        return rows[:consumed], rows[consumed:]
    dated = [r for r in rows if re.match("^" + DATE + "$", r[0])]
    return [r for r in dated if r[0] <= date], [r for r in dated if r[0] > date]


def measure(sk):
    """A dict of the numbers stats prints, or None with problems recorded."""
    rows = load_records(sk)
    entries = changelog(sk)
    if rows is None or not entries:
        if rows is not None:
            sk.problems.append("changelog has no entry")
        return None
    last_v, last_date, _, last_n = entries[-1]
    since = split_at(rows, last_date, last_n)[1]
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
    changed = [(e[1], e[3]) for e in entries if "expect:" in e[2]]
    for v, date, line, consumed in entries:
        # the entries of the latest training that changed something
        if not changed or (date, consumed) != changed[-1] or "expect:" not in line:
            continue
        expect = line.split("expect:", 1)[1].split("— revert if:", 1)[0].lower()
        words = set(re.findall(r"[a-z0-9][a-z0-9_-]*", expect))
        before, after = split_at(rows, date, consumed)
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
        "window": ("after record row %d" % last_n if last_n is not None
                   else "after %s" % last_date),
        "outcomes": outcomes, "tags": tags, "pending": pending, "effects": effects,
        "owner_since": sum(1 for r in since if r[2] in OWNER_OUTCOMES),
        "owner_total": sum(1 for r in rows if r[2] in OWNER_OUTCOMES), "reasons": reasons,
        "skipped": sk.skipped,
    }


def run_stats(root, rel):
    sk = load(root, rel)
    if sk.kind in ("near-miss", "trainer"):
        print("%s: %s" % (rel, NEAR_MISS if sk.kind == "near-miss" else RETIRED))
        return 1
    if sk.kind != "skill":
        print("not a self-training skill")
        return 0
    m = measure(sk)
    if m is None:
        for p in sk.problems:
            print("%s: %s" % (rel, p))
        return 1
    print("skill: %s" % rel)
    print("records: %d" % m["total"])
    print("last training: v%d %s" % m["last"])
    print("records since (%s): %d" % (m["window"], m["since"]))
    if m["skipped"]:
        print("skipped rows that don't parse: %s" % ", ".join(m["skipped"]))
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
    workers = {}
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
            workers[name] = RETIRED
        elif sk.kind == "near-miss":
            workers[name] = "error: %s" % NEAR_MISS
        elif sk.kind == "skill":
            m = measure(sk)
            if m is None:
                workers[name] = "error: %s" % "; ".join(sk.problems)
            elif m["reasons"]:
                workers[name] = "training due (%s)" % "; ".join(m["reasons"])
            else:
                workers[name] = "not due (%d records since v%d)" % (m["since"], m["last"][0])
            if m is not None and m["skipped"]:
                workers[name] += " (skipped rows that don't parse: %s)" % ", ".join(m["skipped"])
    if not workers:
        print("no self-training skills")
    for name in sorted(workers):
        print("%s: %s" % (name, workers[name]))
    return 0


def marked_skills(root):
    """[(name, rel dir)] of the marked worker skills under .claude/skills/ (sorted); [] when
    there is none or the folder is, or lies under, a symlink."""
    base = ".claude/skills"
    folder = os.path.join(root, ".claude", "skills")
    if link_in_path(root, base) or not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        rel = base + "/" + name
        if link_in_path(root, rel + "/SKILL.md") or \
                not os.path.isfile(os.path.join(folder, name, "SKILL.md")):
            continue
        try:
            text = read_rel(root, rel + "/SKILL.md")
        except ValueError:
            continue
        if marker_kind(split_frontmatter(text)[1]) == "skill":
            out.append((name, rel))
    return out


def skill_layout(root):
    """[(folder, records path or None, has a references/ folder)] of the marked skills."""
    out = []
    for _, rel in marked_skills(root):
        try:
            sk = Skill(root, rel)
        except ValueError:
            continue
        path = section_paths(section(sk.secs, "Record") or []).get("Records")
        refs = rel + "/references"
        has_refs = not link_in_path(root, refs) and \
            os.path.isdir(os.path.join(root, *refs.split("/")))
        out.append((rel, safe_rel(path) if path else None, has_refs))
    return out


def snippet(line, needle):
    """The line, stripped, control characters replaced, cut around the first match."""
    text = re.sub(r"[\x00-\x1f\x7f]", "?", line.strip())
    at = text.lower().find(needle)
    if len(text) <= MAX_SNIPPET:
        return text
    start = max(0, min(at - MAX_SNIPPET // 3, len(text) - MAX_SNIPPET))
    return ("..." if start else "") + text[start:start + MAX_SNIPPET] + \
        ("..." if start + MAX_SNIPPET < len(text) else "")


def query_files(sk):
    """[(label, repository-relative path)] of a skill's files: SKILL.md, references/...,
    lessons.md and its records file (labelled from the skill's folder when inside it)."""
    prefix = sk.rel_dir + "/"
    files = [("SKILL.md", prefix + "SKILL.md")]
    files += [(rel[len(prefix):], rel) for rel in reference_files(sk)]
    files.append(("lessons.md", prefix + "lessons.md"))
    path = section_paths(section(sk.secs, "Record") or []).get("Records")
    rel = safe_rel(path) if path else None
    if rel and rel not in (f[1] for f in files):
        files.append((rel[len(prefix):] if rel.startswith(prefix) else rel, rel))
    return files


def run_query(root, term):
    if link_in_path(root, ".claude/skills"):
        print("error: .claude/skills is, or lies under, a symlink; refused", file=sys.stderr)
        return 2
    needle = term.lower()
    skills = marked_skills(root)
    hits = []
    for name, rel in skills:
        try:
            sk = Skill(root, rel)
        except ValueError:
            continue
        for label, frel in query_files(sk):
            try:
                text = read_rel(root, frel)
            except ValueError:
                continue
            is_lessons = frel == rel + "/lessons.md"
            for n, line in enumerate(text.split("\n"), 1):
                at = line.lower().find(needle)
                if at < 0:
                    continue
                lid = ""
                if is_lessons:
                    row = cells(line)
                    if row and re.match(r"^L\d+$", row[0]):
                        lid = " " + row[0]
                hits.append("%s: %s:%d%s: %s" % (name, label, n, lid, snippet(line, needle)))
    if not skills:
        print("no self-training skills")
        return 1
    if not hits:
        print("no hits for %s in %d marked skill%s" % (term, len(skills),
                                                       "" if len(skills) == 1 else "s"))
        return 1
    for h in hits[:MAX_HITS]:
        print(h)
    if len(hits) > MAX_HITS:
        print("(cut: %d more hits; use a longer term)" % (len(hits) - MAX_HITS))
    return 0


def rules_update(text, line, remove):
    """New text with every marked line dropped, then (unless remove) the line at the first
    one's place, or appended (a blank line before it) when there was none and line is True.
    None: delete the file (remove, in a file this created, with only its title left). Line
    endings are kept."""
    eol = "\r\n" if "\r\n" in (text or "") else "\n"
    lines = (text or "").splitlines(True)
    marks = [i for i, ln in enumerate(lines) if RULES_PREFIX in ln]
    if marks:
        first = marks[0]
        created = RULES_MARK_CREATED in lines[first]
        out = []
        for i, ln in enumerate(lines):
            if i in marks:
                if i == first and not remove:
                    out.append((RULES_LINE_CREATED if created else RULES_LINE) +
                               (eol if ln.endswith("\n") else ""))
                continue
            out.append(ln)
        if remove and out and not out[-1].strip() and first >= len(lines) - 1:
            out.pop()  # the blank line added before an appended line
            if out:
                out[-1] = out[-1] if out[-1].endswith("\n") else out[-1] + eol
        result = "".join(out)
        if remove and created and result.strip() == RULES_TITLE:
            return None
        return result
    if remove or not line:
        return text
    if text is None:
        return RULES_TITLE + eol + eol + RULES_LINE_CREATED + eol
    if text and not text.endswith("\n"):
        text += eol
    return text + (eol if text else "") + RULES_LINE + eol


def run_rules_hint(root, remove=False):
    """The one-line instruction: updated in place in AGENTS.md or CLAUDE.md where it is (a
    second copy dropped), else appended to CLAUDE.md (created if missing), only when the
    repository has marked skills. --remove drops it from both."""
    texts = {}
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = os.path.join(root, name)
        if is_link(path) or os.path.isdir(path):
            print("error: %s is a symlink or a folder; refused" % name, file=sys.stderr)
            return 2
        texts[name] = None
        if os.path.lexists(path):
            with open(path, "rb") as fh:
                raw = fh.read()
            try:
                texts[name] = raw.decode("utf-8")
            except UnicodeDecodeError:
                print("error: %s is not UTF-8; add the line by hand" % name, file=sys.stderr)
                return 2
    holders = [n for n in texts if texts[n] and RULES_PREFIX in texts[n]]
    if not holders and not remove and not marked_skills(root):
        print("no self-training skills: nothing written")
        return 0
    new = {}
    for name in texts:
        if remove or holders:
            keep = not remove and name == holders[0]
            stripped = rules_update(texts[name], False, True) if not keep else \
                rules_update(texts[name], True, False)
            new[name] = stripped
        else:
            new[name] = rules_update(texts[name], name == "CLAUDE.md", False)
    for name in texts:
        old = texts[name]
        if new[name] == old:
            print("%s: unchanged" % name)
            continue
        if new[name] is None:
            os.remove(os.path.join(root, name))
            print("%s: removed (it created the file, and only its title was left)" % name)
            continue
        with open(os.path.join(root, name), "wb") as fh:
            fh.write(new[name].encode("utf-8"))
        print("%s: %s" % (name, "created" if old is None else
                          "line removed" if RULES_PREFIX not in new[name] else "line written"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skilltrain.py", description="Self-training skills.")
    ap.add_argument("action", choices=["check", "stats", "due", "query", "rules-hint"])
    ap.add_argument("path", help="check/stats: the skill folder; due, query, rules-hint: the "
                    "repository root")
    ap.add_argument("term", nargs="?", help="query: the term to find")
    ap.add_argument("--root", help="check/stats: the repository root (default: three folders up)")
    ap.add_argument("--triggers-from", metavar="REF",
                    help="check: the quoted trigger phrases of the description at this git ref "
                    "(the skill's and its retired <name>-trainer's) must still be in it")
    ap.add_argument("--remove", action="store_true", help="rules-hint: remove the line")
    args = ap.parse_args(argv)
    if (args.term is not None) != (args.action == "query"):
        ap.error("query takes one TERM; the other actions take none")
    if args.triggers_from is not None and args.action != "check":
        ap.error("--triggers-from is for check")
    if args.remove and args.action != "rules-hint":
        ap.error("--remove is for rules-hint")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except AttributeError:
            pass
    try:
        if args.action in ("due", "query", "rules-hint"):
            root = os.path.abspath(args.path)
            if not os.path.isdir(root):
                raise PathError("no such directory: %s" % args.path)
            if args.action == "query":
                if not args.term.strip():
                    print("error: query needs a non-empty TERM", file=sys.stderr)
                    return 2
                return run_query(root, args.term)
            if args.action == "rules-hint":
                return run_rules_hint(root, args.remove)
            return run_due(root)
        root, rel = resolve(args.path, args.root)
        if args.action == "check":
            return run_check(root, rel, args.triggers_from)
        return run_stats(root, rel)
    except PathError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
