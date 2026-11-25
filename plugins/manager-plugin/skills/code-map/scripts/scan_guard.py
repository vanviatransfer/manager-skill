#!/usr/bin/env python3
"""scan_guard: refuse whole-disk scans, and hand every session and subagent the plugin's paths.

PreToolUse hook on Bash, PowerShell, Glob and Grep (hooks/scan-guard.sh). A command that
recursively scans a filesystem root, a drive root or the home folder (`find /`, `ls -R C:\\`,
`du ~`, `grep -r x /`, `rg x $HOME`, `Get-ChildItem C:\\ -Recurse`, `cmd /c dir /s C:\\`, also in
`bash -c`, `powershell -Command`, pipes, chains, subshells, `$( )` and backticks; a scan with no
path, or with `.`, when the cwd is such a root; Glob or Grep there) is refused: exit 2, one line
naming the code map's and skilltrain's runnable commands and a search limited to the repository.
Why: such a scan can run for hours and exhaust memory, and an agent that doesn't know where
`codemap.py` is tends to look for it with exactly such a scan. It has no off switch, and
`"search_nudge": false` doesn't touch it. Everything else passes; a command it can't parse (an
unbalanced quote) gets only a conservative token check (`find` on a root); any error allows. Hooks
fire for tool calls inside subagents too (the input then carries `agent_id`).

For an allowed recursive scan in Bash (find, grep -r, rg, ls -R, du, tree) that isn't under
`timeout`, it prints once per session (each subagent counts as its own) a non-blocking
additionalContext: prefix `timeout 120`. The state is the search nudge's marker file, own key.

`scan_guard.py start` is the SessionStart and SubagentStart hook (hooks/agent-paths.sh): in a
repository with a `.codemap.json`, a manager-plugin rules marker in AGENTS.md or CLAUDE.md, or a
marked self-training skill, it adds one line with the absolute `codemap.py` and `skilltrain.py`
commands to the session's or the subagent's context; elsewhere it prints nothing.

The search nudge (search_nudge.py) imports `refused` so a command refused here doesn't use up
its once-per-session block. Output goes to stdout; the sh wrapper sends a refusal to stderr.
Standard library only (Python 3.8+); it writes nothing but the hint's marker file.
"""
import json
import os
import posixpath
import re
import shlex
import sys

import search_nudge as sn

# Roots, after norm(): lower case, forward slashes, no trailing slash ("/" is "").
ROOT_RES = [re.compile(p) for p in (
    r"", r"[a-z]:", r"/[a-z]", r"/cygdrive/[a-z]", r"/mnt/[a-z]", r"/root",
    r"(?:[a-z]:|/[a-z]|/cygdrive/[a-z]|/mnt/[a-z])?/(?:home|users)")]
HOME_WORDS = {"~", "$home", "${home}", "$userprofile", "${userprofile}", "$env:userprofile",
              "${env:userprofile}", "$env:homedrive", "${env:homedrive}", "$env:systemdrive",
              "${env:systemdrive}", "%userprofile%", "%homedrive%", "%systemdrive%"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "ash"}
POWERSHELLS = {"powershell", "pwsh"}
PS_LIST = {"get-childitem", "gci", "dir", "ls"}
PS_CD = {"cd", "chdir", "set-location", "sl", "pushd", "push-location"}
# Wrappers that run the rest of the line: the words they take before it.
WRAPPERS = {"sudo": "ugCDhpRrt", "doas": "uC", "nice": "n", "env": "uCS", "nohup": "",
            "stdbuf": "ioe", "builtin": "", "xargs": "dEIiLlnPs"}
TIMED = {"find", "grep", "egrep", "fgrep", "rg", "ls", "du", "tree"}  # for the timeout hint
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1")
HINT = "manager-plugin: long recursive scans: prefix `timeout 120`."
MAX_DEPTH = 4


def norm(path):
    s = path.strip().replace("\\", "/").lower()
    m = re.match(r"^([a-z]):([^/].*)$", s)
    if m:  # Git Bash eats an unquoted backslash: C:\Users arrives as C:Users
        s = "%s:/%s" % m.groups()
    s = re.sub(r"/{2,}", "/", s)
    if s:
        s = posixpath.normpath(s)
    while s.endswith(("/*", "/**")) or s in ("*", "**"):
        s = s.rsplit("/", 1)[0] if "/" in s else "."
    return "" if s == "/" else s.rstrip("/")


def home_values():
    out = set()
    for var in ("HOME", "USERPROFILE"):
        v = os.environ.get(var)
        if v and (v.startswith("/") or sn.is_drive(v.replace("\\", "/") + "/")):
            out.add(norm(v))
    return out


def is_root_norm(s):
    return s in HOME_WORDS or any(r.fullmatch(s) for r in ROOT_RES) or s in home_values()


def absolute(path):
    p = path.replace("\\", "/")
    return p.startswith(("/", "~", "$", "%")) or bool(re.match(r"^[A-Za-z]:", p))


def is_root(path, cwd):
    """True if the path is one of the roots; a relative path counts from cwd (None: unknown)."""
    if not isinstance(path, str) or not path.strip():
        return False
    if is_root_norm(norm(path)):
        return True
    if absolute(path) or cwd is None:
        return False
    return is_root_norm(norm(sn.join(cwd, path)))


def drop_heredocs(cmd):
    """The command without here-document bodies (their lines are text, not commands)."""
    out, ends = [], []
    for line in cmd.split("\n"):
        if ends:
            tab, word = ends[0]
            if (line.lstrip("\t") if tab else line) == word:
                ends.pop(0)
            continue
        out.append(line)
        for m in HEREDOC.finditer(line):
            ends.append((m.group(0).startswith("<<-"), m.group(2)))
    return "\n".join(out)


def substitutions(cmd):
    """The bodies of `$( )` and backticks inside double quotes (simple_commands splits the
    unquoted ones itself; single quotes are literal)."""
    out, quote, i, n = [], None, 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1
        elif c == "'" and quote is None:
            quote = "'"
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif quote == '"' and c == "$" and cmd[i + 1:i + 2] == "(":
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            out.append(cmd[i + 2:j - 1])
            i = j - 1
        elif quote == '"' and c == "`":
            j = cmd.find("`", i + 1)
            if j < 0:
                break
            out.append(cmd[i + 1:j])
            i = j
        i += 1
    return out


def ps_commands(cmd):
    """[(words, after_pipe)] of a PowerShell command: quotes ' and " (backtick escapes), splits
    at ; | & ( ) { } and newlines, drops redirections and comments; `${...}` stays one word."""
    cmds, words = [], []
    word, quote, skip, pipe, i, n = None, None, False, False, 0, len(cmd)

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
            if c == "'" and cmd[i + 1:i + 2] == "'":
                word += "'"
                i += 1
            elif c == "'":
                quote = None
            else:
                word += c
        elif quote == '"':
            if c == "`" and i + 1 < n:
                i += 1
                word += cmd[i]
            elif c == '"':
                quote = None
            else:
                word += c
        elif c == "`" and i + 1 < n:
            i += 1
            word = (word or "") + cmd[i]
        elif c in "'\"":
            quote, word = c, word or ""
        elif c == "$" and cmd[i + 1:i + 2] == "{":
            j = cmd.find("}", i)
            j = n - 1 if j < 0 else j
            word = (word or "") + cmd[i:j + 1]
            i = j
        elif c in " \t\r":
            flush()
        elif c in "<>":
            if word is not None and word.isdigit():
                word = None
            flush()
            while i + 1 < n and cmd[i + 1] in "<>&":
                i += 1
            skip = True
        elif c in ";|&(){}\n":
            flush()
            if words:
                cmds.append((words, pipe))
            words, skip, pipe = [], False, c == "|"
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


def cmd_commands(text):
    """[(words, False)] of a cmd.exe command line: splits at & | ( ), quotes "...", no escapes."""
    out = []
    for part in re.split(r"[&|()]+", text):
        words = re.findall(r'"([^"]*)"|(\S+)', part)
        words = [a or b for a, b in words]
        if words:
            out.append((words, False))
    return out


class Scan:
    """What a command holds: the first refused scan, and whether an untimed scan runs."""

    def __init__(self):
        self.refused = None  # (command, path)
        self.untimed = False

    def check(self, name, paths, cwd, timed=False, hint=True):
        for p in paths:
            if self.refused is None and is_root(p, cwd):
                self.refused = (name, p)
        if paths and hint and not timed and name in TIMED:
            self.untimed = True


def strip_wrappers(words):
    """(words without leading keywords, assignments and wrappers such as `timeout 120`, under
    timeout)."""
    timed = False
    while words:
        w, name = words[0], sn.command_name(words[0])
        if w in sn.PREFIXES or sn.is_assignment(w):
            words = words[1:]
        elif name == "timeout":
            words, timed = words[1:], True
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in ("-s", "-k", "--signal", "--kill-after") \
                    else words[1:]
            words = words[1:]  # the duration
        elif name in WRAPPERS:
            takes, words = WRAPPERS[name], words[1:]
            while words and (words[0].startswith("-") or sn.is_assignment(words[0])):
                a, words = words[0], words[1:]
                if len(a) == 2 and a[1] in takes and words:
                    words = words[1:]
        else:
            break
    return words, timed


def first_operand(args):
    return next((a for a in args if not a.startswith("-")), None)


def scan_unix(scan, name, args, cwd, after_pipe, timed, hint=True):
    """The POSIX scan tools (also when PowerShell or cmd runs them)."""
    if name == "find":
        paths = sn.find_paths(args)
    elif name == "ls":
        flags, _, operands = sn.parse(args, "wIT", {"hide", "ignore", "width", "tabsize"})
        paths = (operands or ["."]) if flags & {"-R", "--recursive"} else None
    elif name == "du":
        flags, values, operands = sn.parse(args, "dBtX", {"max-depth", "block-size",
                                                          "threshold", "exclude",
                                                          "exclude-from", "time-style"})
        paths = None if "--files0-from" in flags else (operands or ["."])
    elif name == "tree":
        flags, values, operands = sn.parse(args, "LPIoHT", {"charset", "filelimit", "timefmt",
                                                            "sort", "fromfile"})
        paths = None if values.get("-L") in ("0", "1") else (operands or ["."])
    elif name in ("fd", "fdfind"):
        flags, values, operands = sn.parse(
            args, "etEdxXSjcb", {"extension", "type", "exclude", "max-depth", "exec",
                                 "exec-batch", "size", "threads", "color", "base-directory",
                                 "search-path", "min-depth", "exact-depth", "changed-within",
                                 "changed-before", "owner", "ignore-file", "format"})
        paths = operands[1:] + [values[k] for k in ("--search-path", "--base-directory")
                                if values.get(k)]
        paths = paths or ["."]
    else:
        paths = sn.search_paths(name, args, after_pipe)
    if paths:
        scan.check(name, paths, cwd, timed, hint)


def new_cwd(arg, cwd):
    if not arg or arg == "-":
        return None if arg else "~"
    if is_root_norm(norm(arg)):
        return arg
    if "$" in arg or "%" in arg or arg.startswith("~"):
        return None
    return None if cwd is None and not absolute(arg) else sn.join(cwd or "/", arg)


def scan_bash(scan, cmd, cwd, depth=0):
    if depth > MAX_DEPTH:
        return
    cmd = drop_heredocs(cmd)
    # An unquoted drive root before a space (`find C:\ -name x`): Git Bash would read `\ ` as an
    # escaped space; the model meant the drive.
    cmd = re.sub(r"(?<![\w\\])([A-Za-z]:)\\(?=[\s;|&)\"']|$)", r"\1/", cmd)
    try:
        shlex.split(cmd, comments=True, posix=True)
    except ValueError:
        return fallback(scan, cmd, cwd)
    for inner in substitutions(cmd):
        scan_bash(scan, inner, cwd, depth + 1)
    for words, after_pipe in sn.simple_commands(cmd):
        words, timed = strip_wrappers(words)
        if not words:
            continue
        name = sn.command_name(words[0])
        args = words[1:]
        if name in ("cd", "pushd"):
            cwd = new_cwd(first_operand(args), cwd)
        elif name in SHELLS:
            shell_c(scan, args, cwd, depth)
        else:
            scan_other(scan, name, args, cwd, after_pipe, timed, depth, hint=True)


def shell_c(scan, args, cwd, depth):
    """`bash -c '<script>'` (also -lc, -ec, ...): scan the script."""
    for k, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
            script = first_operand(args[k + 1:])
            if script:
                scan_bash(scan, script, cwd, depth + 1)
            return


def scan_other(scan, name, args, cwd, after_pipe, timed, depth, hint):
    low = name.lower()
    if low in POWERSHELLS:
        for k, a in enumerate(args):
            if re.fullmatch(r"-(c|com|comm|comma|comman|command)", a, re.I):
                scan_ps(scan, " ".join(args[k + 1:]), cwd, depth + 1)
                break
    elif low == "cmd":
        for k, a in enumerate(args):
            if re.fullmatch(r"/+[ck]", a, re.I):
                scan_cmd(scan, " ".join(args[k + 1:]), cwd, depth + 1)
                break
    elif low == "where" and any(re.fullmatch(r"/+r", a, re.I) for a in args):
        k = next(k for k, a in enumerate(args) if re.fullmatch(r"/+r", a, re.I))
        if k + 1 < len(args):
            scan.check("where", [args[k + 1]], cwd, hint=False)
    elif low in ("find", "ls", "du", "tree", "grep", "egrep", "fgrep", "rg", "ag", "ack", "fd",
                 "fdfind"):
        scan_unix(scan, low, args, cwd, after_pipe, timed, hint)


def ps_param(name, full, least):
    return len(name) >= least and full.startswith(name)


def ps_child_item(args):
    """(recursive, [paths]) of Get-ChildItem's arguments (parameters in any case, abbreviated)."""
    recurse, paths, positional, i = False, [], [], 0
    while i < len(args):
        a = args[i]
        i += 1
        if not (a.startswith("-") and len(a) > 1):
            positional.append(a)
            continue
        name, colon, value = a[1:].partition(":")
        name = name.lower()
        takes = False
        if ps_param(name, "recurse", 1):
            recurse = True
        elif ps_param(name, "depth", 2):
            recurse = takes = True
        elif name in ("p", "lp", "pspath") or ps_param(name, "path", 2) or \
                ps_param(name, "literalpath", 2):
            if not colon and i < len(args):
                value, i = args[i], i + 1
            paths.extend(v for v in value.split(",") if v)
        elif ps_param(name, "filter", 4) or any(ps_param(name, w, 2) for w in
                                                 ("include", "exclude", "attributes")):
            takes = True
        if takes and not colon:
            i += 1
    if positional and not paths:
        paths = [v for v in positional[0].split(",") if v]
    return recurse, paths or ["."]


def scan_ps(scan, cmd, cwd, depth=0):
    if depth > MAX_DEPTH:
        return
    for words, after_pipe in ps_commands(cmd):
        while words and (words[0] in ("&", ".") or words[0].startswith("$") and
                         words[1:2] in (["="], ["+="])):
            words = words[2:] if words[0].startswith("$") else words[1:]
        if not words:
            continue
        name = sn.command_name(words[0]).lower()
        args = words[1:]
        if name in PS_CD:
            arg = next((a for a in args if not a.startswith("-")), None)
            cwd = new_cwd(arg, cwd)
        elif name in PS_LIST:
            recurse, paths = ps_child_item(args)
            if recurse:
                scan.check(name, paths, cwd, hint=False)
        elif name in SHELLS:
            shell_c(scan, args, cwd, depth)
        else:
            scan_other(scan, name, args, cwd, after_pipe, False, depth, hint=False)


def scan_cmd(scan, text, cwd, depth=0):
    if depth > MAX_DEPTH:
        return
    for words, _ in cmd_commands(text):
        name = sn.command_name(words[0]).lower()
        args = words[1:]
        switches = {s.lower() for a in args if a.startswith("/") for s in a.split("/") if s}
        if name == "dir" and "s" in switches:
            paths = [a for a in args if not a.startswith("/")] or ["."]
            scan.check("dir /s", paths, cwd, hint=False)
        elif name == "tree":
            paths = [a for a in args if not a.startswith("/")] or ["."]
            scan.check("tree", paths, cwd, hint=False)
        elif name in ("cd", "chdir"):
            cwd = new_cwd(next((a for a in args if not a.startswith("/")), None) or "", cwd)
        else:
            scan_other(scan, name, args, cwd, False, False, depth, hint=False)


def fallback(scan, cmd, cwd):
    """An unparseable command: only `find` whose first path is a root counts."""
    words = [w.strip("'\"") for w in cmd.split()]
    for k, w in enumerate(words):
        if sn.command_name(w) == "find":
            rest = [a for a in words[k + 1:] if a not in ("-H", "-L", "-P", "--")]
            if rest and not rest[0].startswith("-") and is_root_norm(norm(rest[0])):
                scan.check("find", [rest[0]], None, hint=False)


def glob_base(pattern):
    """(the folder a glob pattern starts in, whether it recurses with **)."""
    parts = pattern.replace("\\", "/").split("/")
    for k, part in enumerate(parts):
        if sn.has_glob(part):
            base = "/".join(parts[:k])
            return (base or ("/" if pattern[:1] in "/\\" else ".")), "**" in "/".join(parts[k:])
    return pattern, False


def inspect(data):
    """A Scan for a hook input, or None when the tool is none of ours."""
    tool, ti = data.get("tool_name"), data.get("tool_input")
    if not isinstance(ti, dict):
        return None
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else None
    scan = Scan()
    path = ti.get("path") if isinstance(ti.get("path"), str) and ti.get("path").strip() else None
    if tool in ("Grep", "Glob"):
        scan.check(tool, [path or "."], cwd, hint=False)
        pattern = ti.get("pattern")
        if tool == "Glob" and isinstance(pattern, str) and pattern:
            full = pattern if absolute(pattern) else (path or ".").rstrip("/\\") + "/" + pattern
            base, recursive = glob_base(full)
            if recursive:
                scan.check(tool, [base], cwd, hint=False)
    elif tool in ("Bash", "PowerShell") and isinstance(ti.get("command"), str):
        if tool == "Bash":
            scan_bash(scan, ti["command"], cwd)
        else:
            scan_ps(scan, ti["command"], cwd)
            scan.untimed = False  # no hint for PowerShell
    else:
        return None
    return scan


def refused(data):
    """(command, path) of the first whole-disk scan in a hook input, or None. Writes nothing;
    the search nudge calls it so a refused command doesn't use up its block."""
    try:
        scan = inspect(data) if isinstance(data, dict) else None
    except Exception:
        return None
    return scan.refused if scan else None


def repo_top(cwd):
    top = sn.find_top(cwd) if isinstance(cwd, str) and cwd else None
    return None if not top or is_root(top, None) else top


def clean(text, limit=60):
    text = re.sub(r"[\x00-\x1f\x7f`]", "?", text)
    return text if len(text) <= limit else text[:limit] + "..."


def commands(top):
    """(code map command, skilltrain command) with the repository filled in, None for one the
    sh wrapper's Python or plugin folder can't give."""
    qtop = sn.quote_path(top, os.name == "nt") if top else None
    code = sn.map_command()
    skill = sn.plugin_command("self-training-skills", "skilltrain.py")
    if code:
        code = "%s query <term>%s" % (code, " --root %s" % qtop if qtop else "")
    if skill:
        skill = "%s query %s -- <term>" % (skill, qtop or "<repo root>")
    return code, skill


def message(found, cwd):
    name, path = found
    top = repo_top(cwd)
    qtop = sn.quote_path(top, os.name == "nt") if top else None
    where = qtop or "<repo path>"
    code, skill = commands(top)
    code = "`%s`" % code if code else "the `manager-plugin:code-map` skill's `query <term>`"
    skill = "`%s`" % skill if skill else ("the `manager-plugin:self-training-skills` skill's "
                                          "`skilltrain.py query <repo root> -- <term>`")
    return ("manager-plugin: scan refused (`%s` over `%s`): a recursive scan of a filesystem, "
            "drive or home root can run for hours and exhaust memory. Code map: %s; skill files: "
            "%s; or search only the repository: `rg <term> %s` or `find %s -name <x>` (prefix "
            "`timeout 120` for a long one). Never search for these scripts: their paths come here "
            "and at session and agent start."
            % (clean(name), clean(path), code, skill, where, where))


def hint_once(data, cwd):
    top = sn.find_top(cwd) if cwd else None
    key = sn.state_key(data, top or "")
    if not key:
        return False
    keep_out = tuple(d for d in (top, cwd, os.getcwd()) if d and os.path.isdir(d))
    return sn.mark(key + "\0timeout-hint", keep_out)


def run(data):
    if not isinstance(data, dict):
        return 0
    scan = inspect(data)
    if scan is None:
        return 0
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else None
    if scan.refused:
        print(message(scan.refused, cwd))
        return 2
    if scan.untimed and hint_once(data, cwd):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": HINT}}))
    return 0


def has_marker(top):
    """True if the repository uses the plugin: a .codemap.json, a manager-plugin rules marker in
    AGENTS.md or CLAUDE.md, or a marked self-training skill."""
    if os.path.isfile(os.path.join(top, sn.CONFIG)):
        return True
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = os.path.join(top, name)
        if os.path.isfile(path) and not os.path.islink(path) and \
                os.path.getsize(path) <= 512 * 1024:
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", "replace")
            if "<!-- manager-plugin:code-map" in text or \
                    "<!-- manager-plugin:self-training-skills" in text:
                return True
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.normpath(os.path.join(here, "..", "..", "self-training-skills", "scripts"))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import skilltrain
    return bool(skilltrain.marked_skills(top))


def find_repo(cwd):
    """The repository top: the nearest folder with .git, else with .codemap.json."""
    top = sn.find_top(cwd)
    if top:
        return top
    d = os.path.abspath(cwd)
    while os.path.isdir(d):
        if os.path.isfile(os.path.join(d, sn.CONFIG)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def start_line(data):
    """The start-context line for a SessionStart or SubagentStart input, or None."""
    cwd = data.get("cwd") if isinstance(data, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    top = find_repo(cwd)
    if not top or not has_marker(top):
        return None
    code, skill = commands(top)
    if not code and not skill:
        return None
    uses = ["code map `%s`" % code] if code else []
    uses += ["skill files `%s`" % skill] if skill else []
    return ("manager-plugin: the plugin's scripts, runnable as given (never search the disk for "
            "these): %s." % "; ".join(uses))


def start(data, event):
    line = start_line(data)
    if line:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                                 "additionalContext": line}}))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        if argv[:1] == ["start"]:
            event = data.get("hook_event_name") if isinstance(data, dict) else None
            if event not in ("SessionStart", "SubagentStart"):
                event = argv[1] if len(argv) > 1 else "SessionStart"
            return start(data, event)
        return run(data)
    except Exception:  # fail open: never block a command on a hook error
        return 0


if __name__ == "__main__":
    sys.exit(main())
