#!/usr/bin/env python3
"""search_nudge: the code map's "map first" Claude Code hook (PreToolUse on Grep, Glob, Bash).

In a repository whose .codemap.json has a "map" and doesn't set "search_nudge": false, the first
broad search of a session (each subagent counts as its own) is blocked once, with one line on
stderr: run the code map's `query` first (the exact command, when the sh wrapper passes the
Python and the plugin folder), then repeat the search. Every later search in that session is
allowed, and a `codemap.py query` or `mentions` run first means no block at all.

JSON hook input on stdin; exit 2 = block, 0 = allow. Any error, or any doubt, allows. Standard
library only (Python 3.8+); the state modules are imported only when a search in a mapped
repository is seen. Nothing is written inside a repository: the per-session state is an empty
marker file under the OS temp dir.

Broad means searching the whole repository or a top-level folder: a path that resolves to the
repository root or a top-level directory (no path counts as the working directory), or a Glob
whose pattern reaches `**` from there. Paths two or more levels deep, files, the vault folder and
the map pages are narrow. `grep` counts only with -r / -R; `rg`, `ag` and `ack` without a path
after a pipe read stdin and don't count; `find -maxdepth 0|1` is a listing.

The skills branch: a search whose path or file pattern targets skill files (`.claude/skills/`,
`SKILL.md`, `lessons.md`, a skill's `references/`, a marked skill's records file) in a
repository with at least one marked self-training skill is blocked once per session the same
way, with its own state, and its line names the runnable `skilltrain.py query <repo root> --
<term>` command (the term taken from the search pattern). Such a
search is handled only by this branch: it never uses up, or gets, the code map's block, and a
code-map block doesn't use up this one. It needs no map: with no `.codemap.json` it is on; with
one (map or not), `"search_nudge": false` turns it off. With no marked skill the branch is not
there: such a search goes to the code-map branch, as before 0.9.5. A wildcard path or file
pattern with a `skills` part counts (`find -path "*/skills/*"`), one with a `references` part only
when a marked skill has a `references/` folder; records count only at a marked skill's `Records:`
path, its folder, or that folder's parent when it is named `skills`.
"""
import json
import os
import posixpath
import re
import sys

CONFIG = ".codemap.json"
STATE_DIR = "manager-plugin-search-nudge"
KEEP_SECONDS = 7 * 24 * 3600
PREFIXES = {"if", "then", "do", "else", "elif", "while", "until", "!", "time", "{", "command",
            "exec", "nohup"}
# Per tool: (short options taking a value, long options taking a value, options giving the
# pattern, so that every operand is a path).
OPTIONS = {
    "grep": ("efmABCdD", {"regexp", "file", "max-count", "after-context", "before-context",
                          "context", "directories", "devices", "include", "exclude",
                          "exclude-dir", "exclude-from", "label", "binary-files"},
             {"-e", "-f", "--regexp", "--file"}),
    "rg": ("efgtTmABCjMEdr", {"regexp", "file", "glob", "iglob", "type", "type-not", "type-add",
                              "type-clear", "max-count", "after-context", "before-context",
                              "context", "threads", "max-columns", "encoding", "replace", "pre",
                              "pre-glob", "colors", "color", "max-depth", "maxdepth",
                              "max-filesize", "path-separator", "sort", "sortr", "engine",
                              "ignore-file", "context-separator", "field-match-separator",
                              "field-context-separator", "dfa-size-limit", "regex-size-limit"},
           {"-e", "-f", "--regexp", "--file", "--files"}),
    "ag": ("ABCGgmp", {"after", "before", "context", "file-search-regex", "ignore", "ignore-dir",
                       "depth", "max-count", "path-to-ignore", "pager", "workers"},
           {"-g", "--file-search-regex"}),
    "ack": ("ABCgm", {"after-context", "before-context", "context", "match", "max-count", "type",
                      "ignore-dir", "noignore-dir", "ignore-file", "type-add", "type-set",
                      "type-del", "output", "pager", "files-from"},
            {"-g", "--match", "-f"}),
    "git grep": ("efABCm", {"max-depth", "threads", "context", "after-context", "before-context",
                            "max-count"},
                 {"-e", "-f"}),
}
OPTIONS["egrep"] = OPTIONS["fgrep"] = OPTIONS["grep"]
INFO = {"--help", "--version", "-V"}
PYTHONS = ("python3", "python", "py -3")  # as the sh wrapper tries them
SKILL_FILES = ("SKILL.md", "lessons.md")
# Options whose value is a file-name pattern: find's tests, rg's globs, grep's --include.
NAME_TESTS = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename"}
NAME_OPTIONS = {"-g", "--glob", "--iglob", "--include"}
MAX_TERM = 60


def is_drive(p):
    return len(p) > 2 and p[0].isalpha() and p[1] == ":" and p[2] == "/"


def has_glob(part):
    return any(c in part for c in "*?[{")


def simple_commands(cmd):
    """[(words, after_pipe)] for each simple command of a shell command, outside quotes.

    Splits at ; & | ( ) ` and newlines, removes quotes and backslashes, drops redirections and
    comments. A here-document's lines still count as commands (a known gap)."""
    cmds, words = [], []
    word, quote, skip, pipe = None, None, False, False
    i, n = 0, len(cmd)

    def flush():
        nonlocal word, skip
        if word is not None:
            if skip:
                skip = False
            else:
                words.append(word)
        word = None

    while i < n:
        c = cmd[i]
        if quote == "'":
            if c == "'":
                quote = None
            else:
                word += c
        elif quote == '"':
            if c == '"':
                quote = None
            elif c == "\\" and i + 1 < n and cmd[i + 1] in '"\\$`\n':
                i += 1
                word += cmd[i]
            else:
                word += c
        elif c == "\\":
            if i + 1 < n:
                i += 1
                if cmd[i] != "\n":
                    word = (word or "") + cmd[i]
        elif c in "'\"":
            quote, word = c, word or ""
        elif c in " \t":
            flush()
        elif c in "<>" or (c == "&" and cmd[i + 1:i + 2] == ">"):
            if word is not None and word.isdigit():
                word = None  # the fd number of 2>file
            flush()
            while i + 1 < n and cmd[i + 1] in "<>&":
                i += 1
            skip = True  # the redirection's target
        elif c in ";&|()`\n":
            flush()
            if words:
                cmds.append((words, pipe))
            words, skip = [], False
            pipe = c == "|" and cmd[i + 1:i + 2] != "|"  # `|` and `|&`, not `||`
            if c == "|" and cmd[i + 1:i + 2] in ("|", "&"):
                i += 1
        elif c == "#" and word is None:
            while i + 1 < n and cmd[i + 1] != "\n":
                i += 1
        else:
            word = (word or "") + c
        i += 1
    flush()
    if words:
        cmds.append((words, pipe))
    return cmds


def parse(args, short, long_):
    """(flags, values, operands) of a command's arguments."""
    flags, values, operands, ended, i = set(), {}, [], False, 0
    while i < len(args):
        a = args[i]
        i += 1
        if ended or a == "-" or not a.startswith("-"):
            operands.append(a)
        elif a == "--":
            ended = True
        elif a.startswith("--"):
            name, eq, value = a[2:].partition("=")
            if not eq and name in long_ and i < len(args):
                value, i = args[i], i + 1
            flags.add("--" + name)
            values["--" + name] = value
        else:
            for j, ch in enumerate(a[1:], 1):
                flags.add("-" + ch)
                if ch in short:
                    value = a[j + 1:]
                    if not value and i < len(args):
                        value, i = args[i], i + 1
                    values["-" + ch] = value
                    break
    return flags, values, operands


def find_paths(args):
    paths, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-H", "-L", "-P") or a.startswith("-O"):
            i += 1
        elif a == "-D":
            i += 2
        elif a.startswith("-") or a in ("!", "("):
            break
        else:
            paths.append(a)
            i += 1
    rest = args[i:]
    if INFO & set(rest):
        return None
    for k, a in enumerate(rest[:-1]):
        if a == "-maxdepth" and rest[k + 1].isdigit() and int(rest[k + 1]) <= 1:
            return None  # a listing of one folder
    return paths or ["."]


def search_paths(name, args, after_pipe):
    """The paths a search command runs over, or None when it is no recursive search."""
    if name == "find":
        return find_paths(args)
    if name == "git":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] in ("-C", "--git-dir", "--work-tree") or \
                    args[i].startswith(("--git-dir=", "--work-tree=")):
                return None  # another repository or folder: can't tell
            i += 2 if args[i] in ("-c", "--namespace") else 1
        if i >= len(args) or args[i] != "grep":
            return None
        name, args = "git grep", args[i + 1:]
    if name not in OPTIONS:
        return None
    short, long_, pattern_opts = OPTIONS[name]
    flags, values, operands = parse(args, short, long_)
    if flags & INFO or (name == "rg" and "-h" in flags):
        return None
    if name in ("grep", "egrep", "fgrep"):
        recursive = flags & {"-r", "-R", "--recursive", "--dereference-recursive"} or \
            "recurse" in (values.get("-d"), values.get("--directories"))
        if not recursive:
            return None
    if not flags & pattern_opts:
        if not operands:
            return None  # no pattern: usage error or help
        operands = operands[1:]
    if operands:
        return operands
    if after_pipe and name in ("rg", "ag", "ack"):
        return None  # searches stdin
    return ["."]


def command_name(word):
    name = word.replace("\\", "/").rsplit("/", 1)[-1]
    return name[:-4] if name.lower().endswith(".exe") else name


def is_map_use(words):
    for k, w in enumerate(words):
        if command_name(w) == "codemap.py":
            sub = next((a for a in words[k + 1:] if not a.startswith("-")), None)
            if sub in ("query", "mentions"):
                return True
    return False


def scan_command(cmd, cwd):
    """(used the map, [(path, cwd)] searched) for a Bash command."""
    used_map, targets = False, []
    for words, after_pipe in simple_commands(cmd):
        while words and (words[0] in PREFIXES or is_assignment(words[0])):
            words = words[1:]
        if not words:
            continue
        if is_map_use(words):
            used_map = True
            continue
        name = command_name(words[0])
        if name in ("cd", "pushd"):
            arg = next((a for a in words[1:] if not a.startswith("-")), None)
            cwd = None if cwd is None or not arg or "$" in arg or arg.startswith("~") \
                else join(cwd, arg)
            continue
        if cwd is None:
            continue  # after `cd -`, `cd ~` or `cd $X`: can't tell where it runs
        for p in search_paths(name, words[1:], after_pipe) or ():
            targets.append((p, cwd))
    return used_map, targets


def is_assignment(word):
    name, eq, _ = word.partition("=")
    return bool(eq and name and (name[0].isalpha() or name[0] == "_")
                and all(ch.isalnum() or ch == "_" for ch in name))


def join(cwd, path):
    p = path.replace("\\", "/")
    if p.startswith("/") or is_drive(p):
        return posixpath.normpath(p)
    return posixpath.normpath(cwd.replace("\\", "/").rstrip("/") + "/" + p)


def rel_parts(path, cwd, top):
    """The path's parts below the repository top level, [] for the top, None outside it."""
    p, t = join(cwd, path), posixpath.normpath(top.replace("\\", "/")).rstrip("/")
    fold = os.name == "nt" or is_drive(t + "/")
    pc, tc = (p.lower(), t.lower()) if fold else (p, t)
    if pc == tc or (not t and p == "/"):
        return []
    if pc.startswith(tc + "/"):
        return [x for x in p[len(t) + 1:].split("/") if x]
    return None


def is_broad(path, cwd, top, cfg, glob_tool=False):
    """True if the search covers the whole repository or a top-level folder."""
    if "$" in path or path.startswith("~"):
        return False
    parts = rel_parts(path, cwd, top)
    if parts is None:
        return False  # outside the repository
    base = []
    for part in parts:
        if not has_glob(part):
            base.append(part)
            continue
        if not (part.startswith("**") if glob_tool else part in ("*", "**")):
            return False  # a pattern for specific files, such as *.py
        break
    else:
        if glob_tool:
            return False  # no wildcard: one exact path
    if len(base) > 1:
        return False
    rel = "/".join(base)
    vault = cfg.get("vault") if isinstance(cfg.get("vault"), str) else ""
    vault = vault.strip("/")
    out = cfg["map"].strip("/")
    pages = posixpath.splitext(out)[0]
    for folder in (vault if vault not in ("", ".") else None, pages):
        if folder and rel and (rel == folder or (rel + "/").startswith(folder + "/")):
            return False  # the vault or the map pages
    if rel == out:
        return False
    return not base or os.path.isdir(os.path.join(top, base[0]))


def find_top(cwd):
    d = os.path.abspath(cwd)
    if not os.path.isdir(d):
        return None
    while True:
        if os.path.lexists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_config(top):
    path = os.path.join(top, CONFIG)
    if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > 65536:
        return None
    with open(path, "rb") as fh:
        cfg = json.loads(fh.read().decode("utf-8"))
    if not isinstance(cfg, dict) or not isinstance(cfg.get("map"), str) or not cfg["map"]:
        return None
    if cfg.get("search_nudge") is False:
        return None
    return cfg


def state_key(data, top):
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    parts = [session]
    for field in ("agent_id", "transcript_path"):
        value = data.get(field)
        parts.append(value if isinstance(value, str) else "")
    parts.append(top)
    return "\0".join(parts)


def within(path, folder):
    path, folder = os.path.normcase(path), os.path.normcase(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def temp_base():
    """The OS temp folder: the first existing one of TMPDIR, TEMP, TMP and the platform
    defaults, as a real path; None if there is none. Unlike tempfile.gettempdir(), it never
    probes a folder by writing a file there and never falls back to the cwd."""
    names = [os.environ.get(v) for v in ("TMPDIR", "TEMP", "TMP")]
    names = [d for d in names if d and os.path.isabs(d)]  # a relative one means the cwd
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        names += [os.path.join(local, "Temp") if local else None,
                  r"C:\TEMP", r"C:\TMP", r"\TEMP", r"\TMP"]
    else:
        names += ["/tmp", "/var/tmp", "/usr/tmp"]
    for d in names:
        if d and os.path.isdir(d):
            return os.path.realpath(d)
    return None


def mark(key, keep_out=()):
    """Record that this session was nudged. True only if this call created the record; False
    when it existed already or can't be written (then nothing is blocked). Nothing is written
    at or below a folder in keep_out (the repository, the input cwd, the process cwd), nor
    inside any other repository, e.g. with TMPDIR set inside a repository."""
    import hashlib
    import stat
    name = STATE_DIR + ("-%d" % os.getuid() if hasattr(os, "getuid") else "")
    base = temp_base()
    if not base or any(within(base, os.path.realpath(d)) for d in keep_out):
        return False
    folder = os.path.join(base, name)
    if find_top(base) or os.path.lexists(os.path.join(folder, ".git")):
        return False  # the temp folder is inside some repository: write nothing there
    try:
        os.mkdir(folder, 0o700)
    except FileExistsError:
        pass
    st = os.lstat(folder)
    if not stat.S_ISDIR(st.st_mode):
        return False
    if hasattr(os, "getuid") and (st.st_uid != os.getuid() or st.st_mode & 0o077):
        return False  # not ours alone: don't trust it
    path = os.path.join(folder, hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()[:40])
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return False
    os.close(fd)
    prune(folder)
    return True


def prune(folder):
    import time
    try:
        limit = time.time() - KEEP_SECONDS
        for entry in os.scandir(folder):
            if entry.is_file(follow_symlinks=False) and entry.stat().st_mtime < limit:
                os.remove(entry.path)
    except OSError:
        pass


def targets_of(data, cwd):
    """(used the map, [(path, cwd, glob_tool)]) for a hook input."""
    tool, ti = data.get("tool_name"), data.get("tool_input")
    if not isinstance(ti, dict):
        return False, []
    path = ti.get("path") if isinstance(ti.get("path"), str) and ti.get("path") else "."
    if tool == "Grep":
        return False, [(path, cwd, False)]
    if tool == "Glob":
        pattern = ti.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return False, []
        p = pattern.replace("\\", "/")
        full = p if p.startswith("/") or is_drive(p) else path.rstrip("/\\") + "/" + p
        return False, [(full, cwd, True)]
    if tool == "Bash" and isinstance(ti.get("command"), str):
        used, found = scan_command(ti["command"], cwd)
        return used, [(p, c, False) for p, c in found]
    return False, []


def scan_skill_search(cmd):
    """([file-name patterns], [search patterns]) of the search commands in a Bash command."""
    names, patterns = [], []
    for words, _ in simple_commands(cmd):
        while words and (words[0] in PREFIXES or is_assignment(words[0])):
            words = words[1:]
        if not words:
            continue
        name, args = command_name(words[0]), words[1:]
        if name == "find":
            for k, a in enumerate(args[:-1]):
                if a in NAME_TESTS:
                    names.append(args[k + 1])
                    patterns.append(args[k + 1])
            continue
        if name == "git" and "grep" in args:
            name, args = "git grep", args[args.index("grep") + 1:]
        if name not in OPTIONS:
            continue
        short, long_, pattern_opts = OPTIONS[name]
        flags, values, operands = parse(args, short, long_)
        for opt in NAME_OPTIONS:
            if opt in values and values[opt]:
                names.append(values[opt])
        for opt in ("-e", "--regexp"):
            if values.get(opt):
                patterns.append(values[opt])
        if not flags & pattern_opts and operands:
            patterns.append(operands[0])
    return names, patterns


def skill_search(data, cwd):
    """([(path, cwd, glob tool)], [file-name patterns], [search patterns]) of a hook input, for
    the skills branch."""
    tool, ti = data.get("tool_name"), data.get("tool_input")
    if not isinstance(ti, dict):
        return [], [], []
    _, targets = targets_of(data, cwd)
    names, patterns = [], []
    if tool == "Grep":
        if isinstance(ti.get("glob"), str):
            names.append(ti["glob"])
        if isinstance(ti.get("pattern"), str):
            patterns.append(ti["pattern"])
    elif tool == "Glob" and isinstance(ti.get("pattern"), str):
        patterns.append(ti["pattern"].replace("\\", "/").rsplit("/", 1)[-1])
    elif tool == "Bash" and isinstance(ti.get("command"), str):
        names, patterns = scan_skill_search(ti["command"])
    return targets, names, patterns


def skill_parts(parts, skills):
    """True if repository-relative path parts (wildcards allowed) name skill files, given the
    marked skills' (folder, records path, has references/) from skilltrain.skill_layout."""
    wild = any(has_glob(p) for p in parts)
    clean = [p for p in parts if p not in ("**", "*")]
    for i in range(len(clean) - 1):
        if clean[i] == ".claude" and clean[i + 1] == "skills":
            return True
    if clean and clean[-1] in SKILL_FILES:
        return True
    if wild and "skills" in clean:
        return True  # e.g. find -path "*/skills/*"
    if wild and "references" in clean and any(refs for _, _, refs in skills):
        return True  # e.g. Glob **/references/*.md, with a marked skill that has references/
    if wild:
        return False
    rel = "/".join(clean)
    for _, records, _ in skills:
        if not records or not rel:
            continue
        folder = posixpath.dirname(records)
        parent = posixpath.dirname(folder)
        if rel == records or (rel + "/").startswith(folder + "/") or \
                (rel == parent and posixpath.basename(parent) == "skills"):
            return True  # the records file, its folder, or the vault's skills/ folder
    return False


def path_parts(targets, names, top):
    """[parts] of the searched paths (inside the repository) and of the file-name patterns."""
    out = []
    for path, cwd, _ in targets:
        if "$" in path or path.startswith("~"):
            continue
        parts = rel_parts(path, cwd, top)
        if parts is not None:
            out.append(parts)
    for name in names:
        out.append([x for x in name.replace("\\", "/").split("/") if x and x != "."])
    return out


SKILL_WORDS = {".claude", "skills", "references", "records.md"} | set(SKILL_FILES)


def skill_term(patterns):
    """A query term from the search's pattern: the pattern itself when it is plain text, else
    its longest run of word characters (3 or more); None when there is none."""
    for p in patterns:
        p = p.strip()
        if re.match(r"^[\w .-]{2,%d}$" % MAX_TERM, p) and p.strip("."):
            return p
        runs = sorted(re.findall(r"\w[\w-]{2,}", p), key=len, reverse=True)
        if runs and len(runs[0]) <= MAX_TERM:
            return runs[0]
    return None


def skill_layout(top):
    """skilltrain.skill_layout(top): (folder, records path, has references/) per marked skill."""
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.normpath(os.path.join(here, "..", "..", "self-training-skills", "scripts"))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import skilltrain
    return skilltrain.skill_layout(top)


def skills_branch(data, cwd, top, key):
    """The skills branch's exit status for a search that targets skill files; None for any
    other search, and when the repository has no marked skill (the code-map branch decides)."""
    targets, names, patterns = skill_search(data, cwd.replace("\\", "/"))
    found = path_parts(targets, names, top)
    if not any(SKILL_WORDS & set(parts) for parts in found):
        return None  # cheap: nothing names a skill file, the skills are never read
    skills = skill_layout(top)
    if not skills or not any(skill_parts(parts, skills) for parts in found):
        return None
    path = os.path.join(top, CONFIG)
    if os.path.isfile(path) and not os.path.islink(path) and os.path.getsize(path) <= 65536:
        with open(path, "rb") as fh:
            cfg = json.loads(fh.read().decode("utf-8"))
        if isinstance(cfg, dict) and cfg.get("search_nudge") is False:
            return 0
    if not key or not mark(key + "\0skills", (top, cwd, os.getcwd())):
        return 0
    cmd = plugin_command("self-training-skills", "skilltrain.py")
    qtop = quote_path(top, os.name == "nt")
    term = skill_term(patterns)
    qterm = quote_path(term) if term else None
    if cmd and qtop:  # `--`: a term may start with a dash
        use = "%s query %s -- %s" % (cmd, qtop, qterm or "<term>")
    else:
        use = ("the `manager-plugin:self-training-skills` skill's `skilltrain.py query <repo "
               "root> -- <term>`")
    print("manager-plugin: skills first: run %s before searching skill files; if that doesn't "
          "answer it, repeat the search and it will be allowed." % use, file=sys.stderr)
    return 2


def run(data):
    if not isinstance(data, dict):
        return 0
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    used_map, targets = targets_of(data, cwd.replace("\\", "/"))
    if not used_map and not targets:
        return 0
    top = find_top(cwd)
    if not top:
        return 0
    skills = skills_branch(data, cwd, top, state_key(data, top))
    if skills is not None:
        return skills  # a search of skill files: the skills branch alone
    cfg = load_config(top)
    key = state_key(data, top)
    if not cfg or not key:
        return 0
    keep_out = (top, cwd, os.getcwd())
    if used_map:
        mark(key, keep_out)
        return 0
    if not any(is_broad(p, c, top, cfg, g) for p, c, g in targets):
        return 0
    if not mark(key, keep_out):
        return 0
    cmd = map_command()
    qtop = quote_path(top, os.name == "nt") if cmd else None
    if cmd and qtop:  # --root: the map's answers are repo-wide even from a subfolder
        use = "%s query <term> --root %s" % (cmd, qtop)
    elif cmd:
        use = "%s query <term>" % cmd
    else:
        use = "the `manager-plugin:code-map` skill's `query <term>`"
    print("manager-plugin: map first: run %s (or read the vault index or the map page %s) before "
          "a broad search; if that doesn't answer it, repeat the search and it will be allowed."
          % (use, cfg["map"]), file=sys.stderr)
    return 2


def quote_path(path, windows=False):
    """The path in double quotes for a shell; on Windows with forward slashes (Git Bash and
    PowerShell take them). None if it holds a control character (the message stays one line)."""
    if any(ord(c) < 32 or ord(c) == 127 for c in path):
        return None
    if windows:
        path = path.replace("\\", "/")
    for c in '\\"$`':
        path = path.replace(c, "\\" + c)
    return '"%s"' % path


def map_command():
    """`<python> "<plugin>/skills/code-map/scripts/codemap.py"`, from the Python and the plugin
    folder the sh wrapper passes (CODEMAP_NUDGE_PYTHON, CODEMAP_NUDGE_ROOT), or None when either
    is missing or the script isn't there."""
    return plugin_command("code-map", "codemap.py")


def plugin_command(skill, name):
    """`<python> "<plugin>/skills/<skill>/scripts/<name>"`, as map_command."""
    python = os.environ.get("CODEMAP_NUDGE_PYTHON")
    root = os.environ.get("CODEMAP_NUDGE_ROOT")
    if python not in PYTHONS or not root or not os.path.isabs(root):
        return None
    script = os.path.normpath(os.path.join(root, "skills", skill, "scripts", name))
    if not os.path.isfile(script):
        return None
    quoted = quote_path(script, os.name == "nt")
    return "%s %s" % (python, quoted) if quoted else None


def main():
    try:
        return run(json.loads(sys.stdin.buffer.read().decode("utf-8", "replace")))
    except Exception:  # fail open: never block a search on a hook error
        return 0


if __name__ == "__main__":
    sys.exit(main())
