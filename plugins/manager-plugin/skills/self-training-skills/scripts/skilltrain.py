#!/usr/bin/env python3
"""skilltrain: check and measure a project's self-training skills.

Usage:
  skilltrain.py check SKILL_DIR [--root DIR] [--triggers-from REF] [--migrate]
                                               exit 0 if the skill is well formed, 1 with one
                                               line per problem, 2 for a bad path (or a REF
                                               that isn't a commit, or no git); --migrate first
                                               adds lessons.md's confidence and last-confirmed
                                               columns in place
  skilltrain.py stats SKILL_DIR [--root DIR]   records, outcomes and tags since the last
                                               training, and whether training is due
  check and stats also take --stale-days N (90) and --stale-uses M (20): an active lesson
  whose last-confirmed is more than N days old, or with more than M records rows dated after
  its last-confirmed, gets one "stale lesson" line (never retired by the script)
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
lesson id a rule cites must be in lessons.md and back it: not a hypothesis, and with a verifier
outcome in its evidence (a records row cited as "<date> <context>: <outcome>" that the records
hold, or an owner verdict quoted as owner: "<words>", <date>); a sourced lesson may back a rule
without one while the changelog has only its first entry. An old five-column lessons table reports
these evidence gaps as notes, not problems (see references/lessons-format.md). Invisible or
direction-changing characters (INVISIBLE) in SKILL.md, lessons.md and the records file give one
line per file and line, never stripped: a problem for a bidi control or a stray tag character, a
note for the others; emoji presentation and joiners inside words are allowed (invisible_chars,
strict=False). With --triggers-from REF, every quoted
phrase ("..." or “...”) of the skill's description at REF, and of the description of the folder
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
import unicodedata

MARKER = "<!-- self-training-skill v1 -->"
MARKER_RE = re.compile(r"^<!-- self-training-(skill|trainer) v\d+ -->$")
SECTIONS = ("Purpose", "Steps", "Rules", "Knowledge", "Record", "Changelog")
RECORDS_HEADER = ("date", "context", "outcome", "tags", "note")
LESSONS_HEADER = ("id", "lesson", "label", "evidence", "status", "confidence", "last-confirmed")
# The header before 0.9.12: read as confidence low and last-confirmed unknown.
OLD_LESSONS_HEADER = LESSONS_HEADER[:5]
CONFIDENCE = ("high", "medium", "low")
UNKNOWN = "unknown"
STALE_DAYS = 90
STALE_USES = 20
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
# A verifier outcome a lesson's evidence cites: a records row by its date, context and outcome
# (a review finding, a test or validation failure, an owner verdict), or an owner verdict quoted
# with its date.
VERIFIER_CITE = re.compile(r"\b(" + DATE + r") (phase [^\s:;,|()]+|owner session): "
                           r"(pass|changes-required|failed|owner-good|owner-bad)\b")
OWNER_VERDICT = re.compile(r"owner: (?:\"[^\"\n]+\"|\u201c[^\u201d\n]+\u201d), (" + DATE + r")\b")
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
# Invisible or direction-changing characters, as (first, last) code points: in a skill's text they
# can hide words from whoever reviews it. invisible_chars() also serves the plugin's own text test.
INVISIBLE = ((0x200B, 0x200D), (0x2060, 0x2064), (0xFEFF, 0xFEFF), (0x202A, 0x202E),
             (0x2066, 0x2069), (0x115F, 0x1160), (0x3164, 0x3164), (0xFFA0, 0xFFA0),
             (0xFE00, 0xFE0F), (0xE0000, 0xE007F), (0xE0100, 0xE01EF))
ZWJ = "\u200d"
# Code points taken as emoji for the ZWJ exception (pictographs, symbols, dingbats, arrows and
# shapes blocks; skin-tone modifiers and regional indicators are inside the first range).
EMOJI = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2300, 0x23FF), (0x2B00, 0x2BFF),
         (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C), (0x2049, 0x2049),
         (0x2122, 0x2122), (0x2139, 0x2139))
BIDI = ((0x202A, 0x202E), (0x2066, 0x2069))  # a problem in check; the rest of INVISIBLE: a note
TAG_CHARS = ((0xE0000, 0xE007F),)  # a problem in check outside an RGI_FLAGS sequence
# The only tag sequences allowed: the three RGI subdivision flags (England, Scotland, Wales).
RGI_FLAGS = tuple("\U0001F3F4" + "".join(chr(0xE0000 + ord(c)) for c in code) + "\U000E007F"
                  for code in ("gbeng", "gbsct", "gbwls"))
SELECTORS = "\ufe0e\ufe0f"
KEYCAP_BASES = "0123456789#*"


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


def in_ranges(ch, ranges):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in ranges)


def letter(ch):
    """A non-ASCII letter."""
    return ord(ch) > 127 and ch.isalpha()


def word_join(line, i):
    """Whether the ZWNJ or ZWJ at line[i] stands inside a non-ASCII word: the character before it,
    past any combining marks (a Devanagari virama), is a non-ASCII letter, and so is the one
    after it."""
    before = i - 1
    while before >= 0 and unicodedata.category(line[before]).startswith("M"):
        before -= 1
    return before >= 0 and i + 1 < len(line) and letter(line[before]) and letter(line[i + 1])


def emoji_join(line, i):
    """Whether the ZWJ at line[i] joins two emoji: the character after it is in EMOJI, and so is
    the one before it once variation selectors and skin-tone modifiers are passed over."""
    before = i - 1
    while before >= 0 and (line[before] in SELECTORS or 0x1F3FB <= ord(line[before]) <= 0x1F3FF):
        before -= 1
    return before >= 0 and i + 1 < len(line) and in_ranges(line[before], EMOJI) and \
        in_ranges(line[i + 1], EMOJI)


def invisible_chars(text, strict=True):
    """[(line, column, code point)] of the INVISIBLE characters in a text, 1-based, the column
    counted in characters (lines split at \\n). Always allowed: a BOM (U+FEFF) as the text's
    first character and a ZWJ between two emoji (emoji_join). Strict (the plugin's own text test)
    allows nothing else. Not strict (`check` on a project's skills) also allows a variation
    selector right after an EMOJI character or a keycap base (0-9 # * then U+20E3), a ZWNJ or
    ZWJ inside a non-ASCII word (word_join: Persian, Indic scripts), and the tag characters of
    the three RGI subdivision flags (RGI_FLAGS)."""
    found = []
    for n, line in enumerate(text.split("\n"), 1):
        tagged = set()
        if not strict:
            for flag in RGI_FLAGS:
                at = line.find(flag)
                while at >= 0:
                    tagged.update(range(at + 1, at + len(flag)))
                    at = line.find(flag, at + len(flag))
        for i, ch in enumerate(line):
            if not in_ranges(ch, INVISIBLE) or (n == 1 and i == 0 and ch == "\ufeff"):
                continue
            if ch == ZWJ and emoji_join(line, i):
                continue
            if not strict:
                if i in tagged:
                    continue
                if ch in SELECTORS and i > 0 and (in_ranges(line[i - 1], EMOJI) or (
                        line[i - 1] in KEYCAP_BASES and line[i + 1:i + 2] == "\u20e3")):
                    continue
                if ch in "\u200c\u200d" and word_join(line, i):
                    continue
            found.append((n, i + 1, ord(ch)))
    return found


def char_name(cp):
    """`U+200B ZERO WIDTH SPACE`."""
    name = unicodedata.name(chr(cp), "")
    return "U+%04X%s" % (cp, " " + name if name else "")


def check_invisible(sk):
    """One line per line of SKILL.md, lessons.md and the records file that holds INVISIBLE
    characters (invisible_chars, not strict): a problem when one is a bidi control or a tag
    character, else a note. A file that can't be read is left to the other checks."""
    rels = [sk.rel_dir + "/SKILL.md", sk.rel_dir + "/lessons.md"]
    path = section_paths(section(sk.secs, "Record") or []).get("Records")
    if path and safe_rel(path):
        rels.append(safe_rel(path))
    for rel in rels:
        try:
            text = read_rel(sk.root, rel)
        except (ValueError, OSError):
            continue
        lines, bad = {}, set()
        for n, col, cp in invisible_chars(text, strict=False):
            lines.setdefault(n, []).append("%s at column %d" % (char_name(cp), col))
            if in_ranges(chr(cp), BIDI + TAG_CHARS):
                bad.add(n)
        for n, chars in sorted(lines.items()):
            if n in bad:
                sk.problems.append("%s:%d holds invisible characters (%s): they can hide text "
                                   "from a review; remove them by hand"
                                   % (rel, n, ", ".join(chars)))
            else:
                sk.notes.append("note: %s:%d holds invisible characters (%s): remove them unless "
                                "they belong there" % (rel, n, ", ".join(chars)))


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
        self.notes = []  # note: lines (an old lessons table, stale lessons)
        self.lessons_old = False  # lessons.md has the header before 0.9.12
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
    sk.lessons_old = False
    if not ok:
        ok, rows, _, bad = parse_table(text, OLD_LESSONS_HEADER)
        sk.lessons_old = ok
    if not ok:
        sk.problems.append("lessons: %s lacks the header | %s | and its separator"
                           % (rel, " | ".join(LESSONS_HEADER)))
        return None
    for n in bad:
        sk.problems.append("lessons: %s:%d is a row that doesn't parse" % (rel, n))
    if sk.lessons_old:
        sk.notes.append("note: %s has no confidence and last-confirmed columns: read as low "
                        "and unknown (check --migrate adds them)" % rel)
    out = {}
    for r in rows:
        out[r[0]] = {"label": r[2].lower(), "evidence": r[3], "status": r[4],
                     "confidence": "low" if sk.lessons_old else r[5],
                     "confirmed": UNKNOWN if sk.lessons_old else r[6]}
    return out


def support(evidence, rows):
    """(records rows the evidence cites that the records hold, as (date, context, outcome),
    the cites they don't hold as text, dates of quoted owner verdicts)."""
    held = {(r[0], r[1], r[2]) for r in rows}
    found, missing = [], []
    for m in VERIFIER_CITE.finditer(evidence):
        cite = (m.group(1), m.group(2), m.group(3))
        (found if cite in held else missing).append(cite if cite in held else m.group(0))
    return found, missing, OWNER_VERDICT.findall(evidence)


def confidence(found, owner_dates):
    """high: 2 or more independent verifier outcomes (distinct date and context) or an owner
    verdict; medium: one; low: none."""
    uses = {(d, c) for d, c, _ in found}
    if owner_dates or any(o in OWNER_OUTCOMES for _, _, o in found) or len(uses) >= 2:
        return "high"
    return "medium" if uses else "low"


def last_confirmed(found, owner_dates):
    dates = [d for d, _, _ in found] + list(owner_dates)
    return max(dates) if dates else UNKNOWN


def today():
    return datetime.date.today()


def stale_lines(lessons, rows, days=STALE_DAYS, uses=STALE_USES):
    """One line per active lesson whose last-confirmed is more than `days` old, or with more than
    `uses` records rows dated after last-confirmed (for an unknown one, all rows count)."""
    out = []
    now = today()
    for lid, les in lessons.items():
        if les["status"].lower() != "active":
            continue
        when = les["confirmed"]
        if valid_date(when):
            age = (now - datetime.date(int(when[:4]), int(when[5:7]), int(when[8:]))).days
            later = sum(1 for r in rows if valid_date(r[0]) and r[0] > when)
        else:
            age, later = None, len(rows)
        if (age is not None and age > days) or later > uses:
            out.append("stale lesson %s (last-confirmed %s%s, %d uses since): keep, re-confirm "
                       "or retire it in the next training"
                       % (lid, when, "" if age is None else ", %d days ago" % age, later))
    return out


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
    # the changelog's own problems keep their place after the rules' (as before 0.9.12)
    mark = len(sk.problems)
    entries = changelog(sk)
    changelog_problems = sk.problems[mark:]
    del sk.problems[mark:]
    # An old (five-column) table is no error: its evidence gaps are notes until it is migrated.
    gap = sk.notes.append if sk.lessons_old else sk.problems.append
    note = "note: " if sk.lessons_old else ""
    verified = {}
    reported = set()
    now = today().isoformat()
    for lid, les in (lessons or {}).items():
        if les["confidence"] not in CONFIDENCE:
            sk.problems.append("lessons: %s has confidence %s (one of %s)"
                               % (lid, les["confidence"] or "''", ", ".join(CONFIDENCE)))
        if les["confirmed"] != UNKNOWN and not valid_date(les["confirmed"]):
            sk.problems.append("lessons: %s has last-confirmed %s (YYYY-MM-DD or %s)"
                               % (lid, les["confirmed"] or "''", UNKNOWN))
        elif les["confirmed"] != UNKNOWN and les["confirmed"] > now:
            sk.problems.append("lessons: %s has last-confirmed %s, later than today (%s)"
                               % (lid, les["confirmed"], now))
        if rows is not None:
            found, missing, owner_dates = support(les["evidence"], rows)
            verified[lid] = bool(found or owner_dates)
            if missing:
                reported.add(lid)  # one line for the lesson, not a second one for its rule
                gap("%slessons: %s cites %s, which the records lack"
                    % (note, lid, "; ".join(missing)))
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
                elif lessons[lid]["status"].lower() == "retired":
                    sk.problems.append("rule cites %s, which is retired" % lid)
                elif lid in reported:
                    continue
                elif lessons[lid]["label"] == "hypothesis":
                    reported.add(lid)
                    sk.problems.append("rule cites %s, a hypothesis: a hypothesis never backs a "
                                       "rule" % lid)
                elif lid in verified and not verified[lid] and \
                        not (lessons[lid]["label"] == "sourced" and len(entries) <= 1):
                    reported.add(lid)
                    gap("%srule cites %s, whose evidence cites no verifier outcome (a records "
                        "row as <date> <context>: <outcome>, or owner: \"<words>\", <date>)"
                        % (note, lid))
        elif not OWNER_CITE.search(b):
            sk.problems.append("rule cites no lesson or owner quote: %s" % b[:80])
    sk.problems.extend(changelog_problems)
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
    return rows, lessons


def run_migrate(root, rel):
    """Adds the confidence and last-confirmed columns to an old lessons table in place, their
    values from each row's evidence and the records; every other byte stays. (exit code, done)"""
    sk = load(root, rel)
    if sk.kind != "skill":
        return 0, False
    lrel = rel + "/lessons.md"
    rows = load_records(sk)
    if rows is None:
        for p in sk.problems:
            print("%s: %s" % (rel, p))
        print("%s: --migrate needs the records file" % rel)
        return 1, False
    try:
        read_rel(root, lrel)  # refuses a symlink, a missing or an oversized file
    except ValueError as exc:
        print("%s: lessons: %s" % (rel, exc))
        return 1, False
    path = os.path.join(root, *lrel.split("/"))
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("%s: lessons: %s is not UTF-8; refused" % (rel, lrel))
        return 1, False
    # Split on "\n" only: U+2028, NEL, FF and the like inside a cell are cell text.
    lines = text.split("\n")
    body = [ln[:-1] if ln.endswith("\r") else ln for ln in lines]
    start = next((i for i, ln in enumerate(body) if ln.strip().startswith("|")), None)
    head = cells(body[start].lstrip("\ufeff")) if start is not None else None
    if head is not None and tuple(c.lower() for c in head) == LESSONS_HEADER:
        print("%s: lessons: %s already has the confidence and last-confirmed columns"
              % (rel, lrel))
        return 0, False
    if head is None or tuple(c.lower() for c in head) != OLD_LESSONS_HEADER or \
            start + 1 >= len(body) or not is_separator(body[start + 1]):
        print("%s: lessons: %s has no lessons table header to migrate" % (rel, lrel))
        return 1, False
    def add(i, extra):
        """The line with extra right after its last pipe; what follows the pipe stays."""
        at = body[i].rindex("|") + 1
        return body[i][:at] + extra + body[i][at:]
    new = {start: add(start, " confidence | last-confirmed |"),
           start + 1: add(start + 1, "---|---|")}
    for i in range(start + 2, len(body)):
        if not body[i].strip():
            continue
        if not body[i].strip().startswith("|"):
            break
        r = cells(body[i])
        if r is None or len(r) != len(OLD_LESSONS_HEADER):
            print("%s: lessons: %s:%d doesn't have exactly %d cells; fix it, then migrate"
                  % (rel, lrel, i + 1, len(OLD_LESSONS_HEADER)))
            return 1, False
        found, _, owner_dates = support(r[3], rows)
        new[i] = add(i, " %s | %s |" % (confidence(found, owner_dates),
                                         last_confirmed(found, owner_dates)))
    out = [new[i] + ln[len(body[i]):] if i in new else ln for i, ln in enumerate(lines)]
    with open(path, "wb") as fh:
        fh.write("\n".join(out).encode("utf-8"))
    print("migrated: %s (%d rows: confidence and last-confirmed added)" % (lrel, len(new) - 2))
    return 0, True


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


def run_check(root, rel, triggers_from=None, stale=(STALE_DAYS, STALE_USES)):
    sha = resolve_ref(root, triggers_from) if triggers_from is not None else None
    sk = load(root, rel)
    if sk.kind is None:
        print("not a self-training skill")
        return 0
    notes = sk.notes
    if sk.kind == "near-miss":
        sk.problems.append(NEAR_MISS)
    elif sk.kind == "trainer":
        sk.problems.append(RETIRED)
    else:
        rows, lessons = check_worker(sk)
        if rows is not None and lessons is not None:
            notes.extend("note: " + ln for ln in stale_lines(lessons, rows, *stale))
        check_routing(sk)
        check_invisible(sk)
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
        "skipped": sk.skipped, "rows": rows,
    }


def run_stats(root, rel, stale=(STALE_DAYS, STALE_USES)):
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
    lessons = load_lessons(sk)
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
    if lessons is not None:
        for line in sk.notes + ["note: " + ln for ln in stale_lines(lessons, m["rows"], *stale)]:
            print(line)
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
    ap.add_argument("--migrate", action="store_true",
                    help="check: first add lessons.md's confidence and last-confirmed columns")
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS, metavar="N",
                    help="check/stats: an active lesson last confirmed more than N days ago is "
                    "stale (default %d)" % STALE_DAYS)
    ap.add_argument("--stale-uses", type=int, default=STALE_USES, metavar="M",
                    help="check/stats: an active lesson followed by more than M records rows "
                    "since its last confirmation is stale (default %d)" % STALE_USES)
    args = ap.parse_args(argv)
    if (args.term is not None) != (args.action == "query"):
        ap.error("query takes one TERM; the other actions take none")
    if args.triggers_from is not None and args.action != "check":
        ap.error("--triggers-from is for check")
    if args.remove and args.action != "rules-hint":
        ap.error("--remove is for rules-hint")
    if args.migrate and args.action != "check":
        ap.error("--migrate is for check")
    stale = (args.stale_days, args.stale_uses)
    if (stale != (STALE_DAYS, STALE_USES) and args.action not in ("check", "stats")) or \
            min(stale) < 0:
        ap.error("--stale-days and --stale-uses are for check and stats, at least 0")
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
            if args.migrate:
                code, _ = run_migrate(root, rel)
                if code:
                    return code
            return run_check(root, rel, args.triggers_from, stale)
        return run_stats(root, rel, stale)
    except PathError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
