"""Format check of the plugin's eval cases (this folder), without running one:
python3 -m unittest discover -s <this folder>

`claude plugin eval` checks a case only when it is about to run it, which is a paid session, and
`claude plugin validate` does not read this folder. So this test loads every case the way the CLI
(Claude Code 2.1.329; the graders' part read again in 2.1.330) does and holds it to that CLI's
case format:

- A case is a folder below the eval folder with a `case.yaml`, a `prompt.md` or `graders/*.md`, in
  any mix. `prompt.md` frontmatter may hold the top-level keys `schema_version`, `name`,
  `description`, `tags`, `plugins`, `runs`, `expected_outcome` and the execution keys `model`,
  `max_turns`, `timeout_seconds`, `allowed_tools`, `disallowed_tools`, `artifact_publish`,
  `growthbook_overrides`, `append_system_prompt`, `env`; its body is the prompt. They are laid
  over `case.yaml` (without one: `schema_version: "1.1"`, `name: <folder name>`), which alone can
  hold `context` (`scaffold_script`, `history_file`, `add_dirs`).
- `graders/<name>.md` with frontmatter is one grader, named after the file; its body is the
  `criteria` of an `llm` or `baseline` grader and the `pattern` of a `regex` one. Types and keys:
  `regex` (`target`, `pattern`, `flags`, `match`), `tool_order` (`before`, `after`), `tool_used`
  (`tool`, `input_match`, `min`, `max`), `file_exists` (`path`, `exists`), `llm` (`criteria`,
  `focus`), `baseline` (`baseline_file`, `criteria`); all take `weight` and `arm`.
- Limits: `max_turns` 1-200, `timeout_seconds` 1-3600, `runs` 1-50, at least one grader, grader
  names unique, a schema version of major 1 at most.
- `mocks/<server>/` in the eval folder, the case folder or a folder between them stands in for an
  MCP server: `<tool>.md` answers a tool (frontmatter `type`, `expect`, `error`, `tools`,
  `abort_when`; the body is the canned result, where `{{file:<path>}}` is a file beside it and
  `{input.<field>}` in that path a field of the call), `_tools.json` lists the tools' schemas; a
  closer folder wins.

Stricter than the CLI where the CLI would ignore a mistake: an unknown key is an error anywhere, a
tool a grader names must be one the case allows (also for a must-not grader, which a withheld tool
would pass for nothing), and every mocked tool needs its schema. A weight is a whole number here.

What the graders see (2.1.330): `tool_used` and `tool_order` count the tool calls of every
`assistant` event of the run, a subagent's as well as the orchestrator's. A `regex` grader on
`trace` reads the events as JSON, one per line, and an orchestrator's event is one with
`"parent_tool_use_id":null`; that is how the manager cases tell whose `Edit` or `Write` it was.

The files are read with a small subset of YAML (`key: value` lines at column 0; a value is a plain
word or sentence, an integer, true/false, a quoted string, or a one-line `[list]` or `{mapping}`
of those), which reads the same in every YAML parser. A file that needs more fails here rather
than being half read. Regular expressions are compiled with Python's `re`, the nearest offline
stand-in for the JavaScript engine that runs them.

The scaffold scripts are run (bash and git only, in a temporary folder): the commits they build
must be the ones the mocks and graders name. Standard library only, Python 3.8+.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # portability.py, in the plugin folder
import portability  # noqa: E402
PLUGIN = os.path.dirname(HERE)
README = os.path.join(PLUGIN, "..", "..", "README.md")
BACKENDS = os.path.join(PLUGIN, "skills", "manager", "references", "github-backends.md")
PLAN_PY = os.path.join(PLUGIN, "skills", "living-plan", "scripts", "plan.py")

# The invariants the plan asks cases for, as the tags the cases carry.
INVARIANTS = ("general-purpose-spawn", "reviewer-every-round", "pinned-merge", "fix-round-brake",
              "orchestrator-no-edit")
# Whether the project's validation passes at the candidate a manager-run scaffold leaves.
CANDIDATE_PASSES = {"review-before-pinned-merge": True, "fix-round-brake": False}

PROMPT_TOP = ("schema_version", "name", "description", "tags", "plugins", "runs",
              "expected_outcome")
PROMPT_EXECUTION = ("model", "max_turns", "timeout_seconds", "allowed_tools", "disallowed_tools",
                    "artifact_publish", "growthbook_overrides", "append_system_prompt", "env")
CASE_KEYS = PROMPT_TOP + ("context", "execution", "graders")
CONTEXT_KEYS = ("scaffold_script", "history_file", "add_dirs")
GRADER_KEYS = {
    "regex": ("target", "pattern", "flags", "match"),
    "tool_order": ("before", "after"),
    "tool_used": ("tool", "input_match", "min", "max"),
    "file_exists": ("path", "exists"),
    "llm": ("criteria", "focus"),
    "baseline": ("baseline_file", "criteria"),
}
GRADER_REQUIRED = {
    "regex": ("pattern",), "tool_order": ("before", "after"), "tool_used": ("tool",),
    "file_exists": ("path",), "llm": ("criteria",), "baseline": ("baseline_file", "criteria"),
}
BODY_FIELD = {"llm": "criteria", "baseline": "criteria", "regex": "pattern"}
TARGETS = ("trace", "last_message", "files", "mock_calls")
MOCK_KEYS = ("type", "expect", "error", "tools", "abort_when")
# The lines `claude plugin eval init` writes for the author to replace.
TEMPLATE_LINES = ("TODO: describe what the agent should do",
                  "TODO: describe what a successful response looks like",
                  "TODO: replace with the canned result this tool should return")

KEY = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*))?$")
INTEGER = re.compile(r"-?(0|[1-9][0-9]*)$")
RESERVED = re.compile(r"(?i)(null|true|false|yes|no|on|off|y|n)$")
FRONTMATTER = re.compile(r"---[ \t]*\n(.*?\n)?---[ \t]*(?:\n|$)", re.S)
SEGMENT = re.compile(r"[A-Za-z0-9_-]+$")
FILE_TEMPLATE = re.compile(r"\{\{\s*file:((?:[^{}]|\{input\.[A-Za-z0-9_.-]+\})+?)\s*\}\}")
SHA = re.compile(r"\b[0-9a-f]{40}\b")
# A tool call of the orchestrator itself in the trace (see the docstring): the pattern of the
# manager cases' `no-edit`, `no-write` and `trace-shows-the-orchestrator` graders.
ORCHESTRATOR_CALL = (r'^\{"type":\s*"assistant",(?=.*"parent_tool_use_id":\s*null).*'
                     r'\{(?=[^{}]*"type":\s*"tool_use")[^{}]*"name":\s*"%s"')
ORCHESTRATOR_NEVER = {"no-edit": "Edit", "no-write": "Write"}
# The orchestrator's own Bash call whose command names the retro switch's script: the pattern of
# the `retro-switch-read` grader. Inside the call's input it passes over whole strings, so only
# the `command` field is read, whichever field comes first.
RETRO_CALL = (ORCHESTRATOR_CALL % "Bash" + r'[^{}]*"input":\s*\{(?:[^{}"\\]|"(?:[^"\\]|\\.)*")*?'
              r'"command":\s*"(?:[^"\\]|\\.)*retro\.sh')
RETRO_CASES = ["manager-run/review-before-pinned-merge"]
# The suite of reviewer-calibration cases, run only by hand (its run.py).
CALIBRATION = "reviewer-calibration"
# Its tags, one per tier (`run.py --tier base|hard`); every case of both is in its folder.
CALIBRATION_TAGS = (CALIBRATION, CALIBRATION + "-hard")


class FormatError(ValueError):
    """A file is outside the YAML subset, or not shaped as the CLI reads it."""


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def scalar(text, where, flow=False):
    """One scalar of the subset: quoted text, an integer, true/false or plain text."""
    for quote in "'\"":
        if text[:1] == quote:
            inner = text[1:-1]
            plain = inner.replace("''", "") if quote == "'" else inner
            if len(text) < 2 or text[-1] != quote or quote in plain or (quote == '"'
                                                                         and "\\" in inner):
                raise FormatError("%s: not one quoted string: %s" % (where, text))
            return inner.replace("''", "'") if quote == "'" else inner
    if INTEGER.match(text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    if (not text[:1].isalpha() or not text.isprintable() or RESERVED.match(text)
            or ": " in text or " #" in text or text.endswith(":")
            or (flow and re.search(r"[\[\]{},'\"]", text))):
        raise FormatError("%s: quote this value: %s" % (where, text))
    return text


def flow_items(text, where):
    """The items between the brackets of a one-line list or mapping (quotes may hold commas)."""
    items, start, quote = [], 0, ""
    for at, char in enumerate(text):
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "[]{}":
            raise FormatError("%s: a nested collection: %s" % (where, text))
        elif char == ",":
            items.append(text[start:at].strip())
            start = at + 1
    if text.strip():
        items.append(text[start:].strip())
    if quote or "" in items:
        raise FormatError("%s: an open quote or an empty item: %s" % (where, text))
    return items


def value(text, where):
    if text[:1] == "[" and text[-1:] == "]":
        return [scalar(item, where, flow=True) for item in flow_items(text[1:-1], where)]
    if text[:1] == "{" and text[-1:] == "}":
        found = {}
        for item in flow_items(text[1:-1], where):
            match = KEY.match(item)
            if not match or match.group(2) is None or match.group(1) in found:
                raise FormatError("%s: not `key: value`, or a key twice: %s" % (where, item))
            found[match.group(1)] = scalar(match.group(2).strip(), where, flow=True)
        return found
    return scalar(text, where)


def mapping(text, where):
    """{key: value} of `key: value` lines at column 0; empty lines and `#` lines are skipped."""
    found = {}
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY.match(line.rstrip())
        if not match or match.group(2) is None or match.group(1) in found:
            raise FormatError("%s:%d: not `key: value` at column 0, or a key twice: %s"
                              % (where, number, line))
        found[match.group(1)] = value(match.group(2).strip(), "%s:%d" % (where, number))
    return found


def frontmatter(text, where):
    """(the frontmatter's mapping, or None when the file has none; the body below it)."""
    match = FRONTMATTER.match(text)
    if not match:
        if text.startswith("---"):
            raise FormatError("%s: frontmatter is not closed" % where)
        return None, text
    return mapping(match.group(1) or "", where), text[match.end():]


def tree(folder):
    """{path below the folder, with `/`: text} of every file under it."""
    found = {}
    for top, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in names:
            path = os.path.join(top, name)
            found[os.path.relpath(path, folder).replace(os.sep, "/")] = read(path)
    return found


def merge(name, files):
    """The case of a folder's files, {path: text}, laid together as the CLI lays them."""
    if "case.yaml" in files:
        case = mapping(files["case.yaml"], "case.yaml")
    else:
        case = {"schema_version": "1.1", "name": name}
    execution = case.get("execution", {})
    if not isinstance(execution, dict):
        raise FormatError("case.yaml: execution is not a mapping")
    execution = dict(execution)
    if "prompt.md" in files:
        front, body = frontmatter(files["prompt.md"], "prompt.md")
        for key, item in (front or {}).items():
            if key in PROMPT_TOP:
                case[key] = item
            elif key in PROMPT_EXECUTION:
                execution[key] = item
            else:
                raise FormatError("prompt.md: unknown frontmatter key: %s" % key)
        if body.strip():
            execution["prompt"] = body.strip()
    graders = case.get("graders", [])
    if not isinstance(graders, list):
        raise FormatError("case.yaml: graders is not a list")
    graders = list(graders)
    for path in sorted(files):
        if not re.match(r"graders/[^/]+\.md$", path):
            continue
        front, body = frontmatter(files[path], path)
        if front is None:
            continue
        if not isinstance(front.get("type"), str):
            raise FormatError("%s: frontmatter without `type:`" % path)
        grader = dict({"name": path[len("graders/"):-len(".md")]}, **front)
        field = BODY_FIELD.get(front["type"])
        if field and field not in grader and body.strip():
            grader[field] = body.strip()
        graders.append(grader)
    case["execution"] = execution
    if graders:
        case["graders"] = graders
    return case


def is_int(item, low, high=None):
    return (isinstance(item, int) and not isinstance(item, bool) and item >= low
            and (high is None or item <= high))


def is_strings(item):
    return isinstance(item, list) and all(isinstance(entry, str) for entry in item)


def pattern_problem(text):
    try:
        re.compile(text)
    except re.error as error:
        return "does not compile: %s" % error
    return None


def target_ok(item):
    return item in TARGETS or (isinstance(item, dict) and sorted(item) == ["path", "source"]
                               and item["source"] == "file" and isinstance(item["path"], str))


def tool_of(item):
    """(tool name, input pattern or None) of a `before`/`after` value; None if misshapen."""
    if isinstance(item, str):
        return item, None
    if (isinstance(item, dict) and isinstance(item.get("tool"), str)
            and set(item) <= {"tool", "input_match"}
            and isinstance(item.get("input_match", ""), str)):
        return item["tool"], item.get("input_match")
    return None


def grader_problems(grader):
    kind, name = grader.get("type"), grader.get("name")
    if kind not in GRADER_KEYS:
        return ["grader %s: unknown type %r" % (name, kind)]
    found = []
    allowed = ("type", "name", "weight", "arm") + GRADER_KEYS[kind]
    found += ["unknown key %s" % key for key in grader if key not in allowed]
    found += ["no %s" % key for key in GRADER_REQUIRED[kind] if key not in grader]
    for key in ("name", "pattern", "flags", "match", "tool", "input_match", "path", "criteria",
                "baseline_file"):
        if key in grader and not (isinstance(grader[key], str) and grader[key]):
            found.append("%s is not a non-empty string" % key)
    if not is_int(grader.get("weight", 1), 1):
        found.append("weight is not a positive number")
    if grader.get("arm", "both") not in ("with-only", "both"):
        found.append("arm is not with-only or both")
    for key in ("target", "focus"):
        if key in grader and not target_ok(grader[key]):
            found.append("%s is not one of %s or {source: file, path}" % (key, ", ".join(TARGETS)))
    if not re.match(r"[dgimsuvy]*$", str(grader.get("flags", ""))):
        found.append("flags are not JavaScript RegExp flags")
    if not re.match(r"(contains|not_contains|count:[0-9]+)$", str(grader.get("match",
                                                                              "contains"))):
        found.append("match is not contains, not_contains or count:N")
    patterns = [grader.get("pattern"), grader.get("input_match")]
    for key in ("before", "after"):
        if key in grader:
            tool = tool_of(grader[key])
            if tool is None:
                found.append("%s is not a tool name or {tool, input_match}" % key)
            else:
                patterns.append(tool[1])
    for text in patterns:
        problem = isinstance(text, str) and pattern_problem(text)
        if problem:
            found.append("pattern %s" % problem)
    for key in ("min", "max"):
        if key in grader and not is_int(grader[key], 0):
            found.append("%s is not a count" % key)
    if is_int(grader.get("min"), 0) and is_int(grader.get("max"), 0) and (grader["min"]
                                                                           > grader["max"]):
        found.append("min is above max")
    if "exists" in grader and not isinstance(grader["exists"], bool):
        found.append("exists is not true or false")
    if any(line in str(grader.get(key, "")) for line in TEMPLATE_LINES
           for key in ("criteria", "pattern")):
        found.append("still the init template")
    return ["grader %s: %s" % (name, problem) for problem in found]


def problems(case):
    """What the CLI's case format refuses in a merged case, one line each; none: a valid case."""
    found = ["unknown key %s" % key for key in case if key not in CASE_KEYS]
    version = case.get("schema_version")
    if not isinstance(version, str) or not re.match(r"[01](\.|$)", version):
        found.append("schema_version is not a string of major version 1 or lower")
    if not (isinstance(case.get("name"), str) and case["name"]):
        found.append("no name")
    for key in ("description", "expected_outcome"):
        if key in case and not isinstance(case[key], str):
            found.append("%s is not a string" % key)
    for key in ("tags", "plugins"):
        if key in case and not is_strings(case[key]):
            found.append("%s is not a list of strings" % key)
    if not is_int(case.get("runs", 3), 1, 50):
        found.append("runs is not 1-50")
    context = case.get("context", {})
    if not isinstance(context, dict):
        found.append("context is not a mapping")
    else:
        found += ["unknown key context.%s" % key for key in context if key not in CONTEXT_KEYS]
        for key in ("scaffold_script", "history_file"):
            if key in context and not (isinstance(context[key], str) and context[key]):
                found.append("context.%s is not a path" % key)
        if not is_strings(context.get("add_dirs", [])):
            found.append("context.add_dirs is not a list of strings")
    execution = case.get("execution", {})
    found += ["unknown key execution.%s" % key for key in execution
              if key not in PROMPT_EXECUTION + ("prompt",)]
    prompt = execution.get("prompt")
    if not (isinstance(prompt, str) and prompt.strip()):
        found.append("no prompt")
    elif any(line in prompt for line in TEMPLATE_LINES):
        found.append("the prompt is still the init template")
    if not is_int(execution.get("max_turns", 10), 1, 200):
        found.append("max_turns is not 1-200")
    if not is_int(execution.get("timeout_seconds", 300), 1, 3600):
        found.append("timeout_seconds is not 1-3600")
    for key in ("model", "append_system_prompt"):
        if key in execution and not isinstance(execution[key], str):
            found.append("execution.%s is not a string" % key)
    for key in ("allowed_tools", "disallowed_tools"):
        if key in execution and not is_strings(execution[key]):
            found.append("execution.%s is not a list of strings" % key)
    if not isinstance(execution.get("artifact_publish", False), bool):
        found.append("execution.artifact_publish is not true or false")
    env = execution.get("env", {})
    if not (isinstance(env, dict) and all(isinstance(item, str) for item in env.values())):
        found.append("execution.env is not a mapping of strings")
    if not isinstance(execution.get("growthbook_overrides", {}), dict):
        found.append("execution.growthbook_overrides is not a mapping")
    graders = case.get("graders", [])
    if not graders:
        found.append("no grader")
    names = [grader.get("name") for grader in graders if isinstance(grader, dict)]
    found += ["grader name twice: %s" % name for name in sorted(set(names))
              if names.count(name) > 1]
    for grader in graders:
        found += grader_problems(grader) if isinstance(grader, dict) else ["a grader is not a "
                                                                           "mapping"]
    return found


def case_folders(skip=(CALIBRATION,)):
    """The folders below this one that hold a case, as paths with `/` from here, sorted; without
    the reviewer-calibration suite, which `test_reviewer_calibration.py` holds to its own rules
    (`skip=()`: every case)."""
    found = []
    for top, dirs, names in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in ("mocks", "results", "graders",
                                                      "__pycache__")
                         and not (top == HERE and d in skip))
        if top != HERE and ("case.yaml" in names or "prompt.md" in names
                            or os.path.isdir(os.path.join(top, "graders"))):
            found.append(os.path.relpath(top, HERE).replace(os.sep, "/"))
    return found


def load(folder):
    path = os.path.join(HERE, *folder.split("/"))
    return merge(os.path.basename(path), tree(path))


def graded_tools(case):
    """The tool names the case's graders look for in the run."""
    found = set()
    for grader in case["graders"]:
        if grader["type"] == "tool_used":
            found.add(grader["tool"])
        elif grader["type"] == "tool_order":
            found.update(tool_of(grader[key])[0] for key in ("before", "after"))
    return found


def trace_event(kind, parent, blocks):
    """One event of a run's stream as Claude Code 2.1.330 writes it: an `assistant` or `user`
    message with its `parent_tool_use_id` (None: the orchestrator's own), or a `system` line."""
    if kind == "system":
        return {"type": "system", "subtype": "task_notification", "summary": blocks,
                "session_id": "s", "uuid": "u"}
    message = {"role": kind, "content": blocks}
    if kind == "assistant":
        message = dict({"model": "m", "id": "msg_1", "type": "message"}, **message)
    return {"type": kind, "message": message, "parent_tool_use_id": parent, "session_id": "s",
            "uuid": "u"}


def tool_use(name, tool_input):
    return {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input,
            "caller": {"type": "direct"}}


def trace_text(events):
    """What a `regex` grader on `trace` reads: every event as compact JSON, one per line."""
    return "\n".join(json.dumps(event, separators=(",", ":"), ensure_ascii=False)
                     for event in events)


def mocks(folder):
    """The stand-ins a case runs with: ({server: {tool: (responder path, frontmatter, body)}},
    {server: {tool: its `_tools.json` entry}}), from every `mocks/` folder between this folder
    and the case's; the closer one wins."""
    responders, listings, at = {}, {}, HERE
    for part in [""] + folder.split("/"):
        at = os.path.join(at, part)
        root = os.path.join(at, "mocks")
        for server in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if not os.path.isdir(os.path.join(root, server)):
                continue
            for name in sorted(os.listdir(os.path.join(root, server))):
                path = os.path.join(root, server, name)
                if name == "_tools.json":
                    for entry in json.loads(read(path))["tools"]:
                        listings.setdefault(server, {})[entry["name"]] = entry
                elif name.endswith(".md"):
                    front, body = frontmatter(read(path), path)
                    responders.setdefault(server, {})[name[:-3]] = (path, front or {}, body)
    return responders, listings


def run_scaffold(folder, work):
    """(exit code, standard error) of a case's scaffold script run as the CLI runs it: `bash
    <script>` in the run's working folder, with a home of its own and no system git config."""
    script = os.path.join(HERE, *(folder.split("/") + [load(folder)["context"]["scaffold_script"]]))
    home = os.path.dirname(work)
    temp = os.path.join(os.path.dirname(home), "tmp")
    os.makedirs(temp, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "USERPROFILE": home, "TMPDIR": temp,
           "TMP": temp, "TEMP": temp, "TERM": "dumb", "GIT_CONFIG_NOSYSTEM": "1"}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    done = subprocess.run([portability.bash(), script], cwd=work, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=120)
    return done.returncode, done.stderr.decode("utf-8", "replace")


def scaffold(folder, into):
    """The working folder of a new run below `into`, after the case's scaffold script."""
    work = os.path.join(into, "home", "cwd")
    os.makedirs(work)
    code, err = run_scaffold(folder, work)
    if code:
        raise AssertionError("%s: scaffold exit %d: %s" % (folder, code, err))
    return work


def git(work, *args, ok=(0,)):
    """(exit code, output) of a git command in a scaffolded folder, whose `.git` is trusted here
    because this test has just built it."""
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=os.path.dirname(work))
    done = subprocess.run(["git"] + list(args), cwd=work, env=env, capture_output=True)
    if done.returncode not in ok:
        raise AssertionError("git %s: %s" % (" ".join(args),
                                             done.stderr.decode("utf-8", "replace")))
    return done.returncode, done.stdout.decode("utf-8").strip()


class SubsetTest(unittest.TestCase):
    """The YAML subset: what it reads, and that it refuses what it would read differently from a
    YAML parser."""

    def test_values(self):
        text = ("# a comment\nname: two words\nruns: 3\nflag: true\nversion: \"1.1\"\n\n"
                "pattern: '\"a\":\\s*\"b\", it''s [x] # no comment'\n"
                "tools: [Read, 'Bash(git log:*)', mcp__github__merge_pull_request]\nnone: []\n"
                "before: {tool: Agent, input_match: 'a, b: {c}'}\nmatch: count:0\n")
        self.assertEqual(mapping(text, "sample"), {
            "name": "two words", "runs": 3, "flag": True, "version": "1.1",
            "pattern": "\"a\":\\s*\"b\", it's [x] # no comment",
            "tools": ["Read", "Bash(git log:*)", "mcp__github__merge_pull_request"], "none": [],
            "before": {"tool": "Agent", "input_match": "a, b: {c}"}, "match": "count:0"})

    def test_what_is_outside_the_subset(self):
        for text in ("key:\n", "key:\n  nested: 1\n", "  key: indented\n", "key: |\n  block\n",
                     "key: a # comment\n", "key: a: b\n", "key: 1.5\n", "key: null\n",
                     "key: Yes\n", "key: ~\n", "key: 2026-01-05\n", "key: &anchor a\n",
                     "key: *alias\n", "key: !tag a\n", "key: 'open\n", "key: 'a' b\n",
                     "key: \"a\\n\"\n", "key: [a, [b]]\n", "key: [a, ]\n", "key: {a: {b: c}}\n",
                     "key: {a}\n", "key: [a\n", "key: 1\nkey: 2\n", "- item\n", "---\nkey: a\n",
                     "key: [it's, a]\n", "key: -x\n", "key: 007\n"):
            with self.subTest(text=text):
                self.assertRaises(FormatError, mapping, text, "sample")

    def test_frontmatter(self):
        self.assertEqual(frontmatter("---\ntype: llm\n---\n\nPass if so.\n", "x"),
                         ({"type": "llm"}, "\nPass if so.\n"))
        self.assertEqual(frontmatter("---\n---\nbody\n", "x"), ({}, "body\n"))
        self.assertEqual(frontmatter("no frontmatter\n---\n", "x"), (None, "no frontmatter\n---\n"))
        self.assertRaises(FormatError, frontmatter, "---\ntype: llm\nbody\n", "x")


class FormatTest(unittest.TestCase):
    """The loader and the checker on a small case: valid as it stands, refused once broken."""

    FILES = {
        "prompt.md": "---\nmax_turns: 5\nallowed_tools: [Read, Write]\n---\nWrite `out.md`.\n",
        "graders/made.md": "---\ntype: file_exists\npath: out.md\n---\n",
        "graders/said.md": "---\ntype: llm\nweight: 2\n---\nIt says the file is written.\n",
        "graders/notes.md": "Not a grader: no frontmatter.\n",
    }

    def case(self, changes=None):
        """The sample case with files replaced, {path: text}; a text of None removes the file."""
        files = dict(self.FILES, **(changes or {}))
        return merge("sample", {path: text for path, text in files.items() if text is not None})

    def test_a_valid_case(self):
        case = self.case()
        self.assertEqual(case, {
            "schema_version": "1.1", "name": "sample",
            "execution": {"max_turns": 5, "allowed_tools": ["Read", "Write"],
                          "prompt": "Write `out.md`."},
            "graders": [{"name": "made", "type": "file_exists", "path": "out.md"},
                        {"name": "said", "type": "llm", "weight": 2,
                         "criteria": "It says the file is written."}]})
        self.assertEqual(problems(case), [])

    def test_case_yaml_is_the_base_and_prompt_md_lies_over_it(self):
        case = self.case({"case.yaml": "schema_version: \"1.0\"\nname: named\nruns: 2\n"
                                       "context: {scaffold_script: scaffold.sh}\n",
                          "prompt.md": "---\nruns: 4\ntags: [a]\n---\nDo it.\n"})
        self.assertEqual((case["name"], case["runs"], case["tags"], case["context"]),
                         ("named", 4, ["a"], {"scaffold_script": "scaffold.sh"}))
        self.assertEqual(problems(case), [])

    def test_what_the_loader_refuses(self):
        for changes in ({"prompt.md": "---\ncontext: {scaffold_script: a.sh}\n---\nDo it.\n"},
                        {"prompt.md": "---\nprompt: Do it.\n---\n"},
                        {"graders/made.md": "---\npath: out.md\n---\n"},
                        {"graders/made.md": "---\ntype: file_exists\npath: out.md\n"}):
            with self.subTest(changes=changes):
                self.assertRaises(FormatError, self.case, changes)

    def test_what_the_checker_refuses(self):
        grader = "---\ntype: %s\n%s---\n%s"
        for problem, changes in (
                ("no prompt", {"prompt.md": "---\nmax_turns: 5\n---\n"}),
                ("the prompt is still the init template",
                 {"prompt.md": "TODO: describe what the agent should do\n"}),
                ("max_turns is not 1-200", {"prompt.md": "---\nmax_turns: 201\n---\nDo it.\n"}),
                ("max_turns is not 1-200", {"prompt.md": "---\nmax_turns: 0\n---\nDo it.\n"}),
                ("timeout_seconds is not 1-3600",
                 {"prompt.md": "---\ntimeout_seconds: 3601\n---\nDo it.\n"}),
                ("runs is not 1-50", {"prompt.md": "---\nruns: 51\n---\nDo it.\n"}),
                ("tags is not a list of strings", {"prompt.md": "---\ntags: one\n---\nDo it.\n"}),
                ("execution.allowed_tools is not a list of strings",
                 {"prompt.md": "---\nallowed_tools: Read\n---\nDo it.\n"}),
                ("schema_version is not a string of major version 1 or lower",
                 {"case.yaml": "schema_version: \"2.0\"\nname: sample\n"}),
                ("schema_version is not a string of major version 1 or lower",
                 {"case.yaml": "name: sample\n"}),
                ("no name", {"case.yaml": "schema_version: \"1.1\"\n"}),
                ("unknown key contxt", {"case.yaml": "schema_version: \"1.1\"\nname: sample\n"
                                                     "contxt: {scaffold_script: a.sh}\n"}),
                ("unknown key context.script",
                 {"case.yaml": "schema_version: \"1.1\"\nname: sample\ncontext: {script: a.sh}\n"}),
                ("no grader", {"graders/made.md": None, "graders/said.md": None}),
                ("grader name twice: said",
                 {"graders/made.md": grader % ("file_exists", "name: said\npath: out.md\n", "")}),
                ("grader made: unknown type 'exists'",
                 {"graders/made.md": grader % ("exists", "path: out.md\n", "")}),
                ("grader made: unknown key pattern",
                 {"graders/made.md": grader % ("file_exists", "path: a\npattern: b\n", "")}),
                ("grader made: no path", {"graders/made.md": grader % ("file_exists", "", "")}),
                ("grader made: exists is not true or false",
                 {"graders/made.md": grader % ("file_exists", "path: a\nexists: 1\n", "")}),
                ("grader said: no criteria", {"graders/said.md": grader % ("llm", "", "")}),
                ("grader said: still the init template",
                 {"graders/said.md": grader % (
                     "llm", "", "TODO: describe what a successful response looks like\n")}),
                ("grader said: focus is not one of trace, last_message, files, mock_calls or "
                 "{source: file, path}",
                 {"graders/said.md": grader % ("llm", "focus: transcript\n", "Pass.\n")}),
                ("grader said: weight is not a positive number",
                 {"graders/said.md": grader % ("llm", "weight: 0\n", "Pass.\n")}),
                ("grader said: arm is not with-only or both",
                 {"graders/said.md": grader % ("llm", "arm: with\n", "Pass.\n")}),
                ("grader said: no pattern", {"graders/said.md": grader % ("regex", "", "")}),
                ("grader said: match is not contains, not_contains or count:N",
                 {"graders/said.md": grader % ("regex", "match: absent\n", "a\n")}),
                ("grader said: flags are not JavaScript RegExp flags",
                 {"graders/said.md": grader % ("regex", "flags: x\n", "a\n")}),
                ("grader said: pattern does not compile",
                 {"graders/said.md": grader % ("regex", "", "(a\n")}),
                ("grader said: no tool", {"graders/said.md": grader % ("tool_used", "", "")}),
                ("grader said: max is not a count",
                 {"graders/said.md": grader % ("tool_used", "tool: Read\nmax: -1\n", "")}),
                ("grader said: min is above max",
                 {"graders/said.md": grader % ("tool_used", "tool: Read\nmin: 2\nmax: 1\n", "")}),
                ("grader said: no after",
                 {"graders/said.md": grader % ("tool_order", "before: Read\n", "")}),
                ("grader said: after is not a tool name or {tool, input_match}",
                 {"graders/said.md": grader % ("tool_order",
                                                "before: Read\nafter: {name: Write}\n", "")})):
            with self.subTest(problem=problem):
                found = problems(self.case(changes))
                self.assertTrue(any(item.startswith(problem) for item in found), found)

    def test_targets_and_tool_matchers(self):
        grader = "---\ntype: %s\n%s---\n%s"
        case = self.case({
            "graders/made.md": grader % ("regex", "target: {source: file, path: out.md}\n"
                                                  "match: count:2\nflags: gi\n", "^x$\n"),
            "graders/said.md": grader % ("tool_order", "before: {tool: Read, input_match: 'a.md'}\n"
                                                       "after: Write\narm: with-only\n", "")})
        self.assertEqual(problems(case), [])
        self.assertEqual(graded_tools(case), {"Read", "Write"})


class CasesTest(unittest.TestCase):
    """The cases of this folder."""

    @classmethod
    def setUpClass(cls):
        cls.cases = {folder: load(folder) for folder in case_folders()}

    def test_every_case_is_valid(self):
        self.assertGreaterEqual(len(self.cases), 3)
        for folder, case in self.cases.items():
            with self.subTest(case=folder):
                self.assertEqual(problems(case), [])
                self.assertEqual(case["name"], folder.split("/")[-1])
        names = [case["name"] for case in self.cases.values()]
        self.assertEqual(len(set(names)), len(names), "the CLI tells cases apart by name")

    def test_every_invariant_has_a_case(self):
        tags = [tag for case in self.cases.values() for tag in case.get("tags", [])]
        self.assertEqual(sorted(set(tags)), sorted(INVARIANTS))
        self.assertFalse(set(tags) & set(CALIBRATION_TAGS))
        self.assertFalse(set(INVARIANTS) & set(CALIBRATION_TAGS))
        for case in self.cases.values():
            self.assertTrue(case.get("tags") and case.get("description"), case["name"])

    def test_both_calibration_tiers_are_left_out(self):
        """Every case with a reviewer-calibration tag (either tier) is in the suite's folder,
        which these checks skip."""
        tagged = {folder: load(folder)["tags"] for folder in case_folders(skip=())
                  if set(load(folder).get("tags", [])) & set(CALIBRATION_TAGS)}
        self.assertEqual(sorted({tag for tags in tagged.values() for tag in tags}),
                         sorted(CALIBRATION_TAGS))
        for folder in tagged:
            self.assertTrue(folder.startswith(CALIBRATION + "/"), folder)
            self.assertNotIn(folder, self.cases)

    def test_the_tools_a_grader_names_are_the_run_s_to_call(self):
        """A tool the case does not allow is withheld from the model: a grader that wants a call
        can never pass, and one that forbids a call passes for nothing. A mocked MCP tool is
        allowed by its responder."""
        for folder, case in self.cases.items():
            allowed = {tool.split("(")[0] for tool in case["execution"].get("allowed_tools", [])}
            mocked = {"mcp__%s__%s" % (server, tool)
                      for server, tools in mocks(folder)[0].items() for tool in tools}
            with self.subTest(case=folder):
                self.assertEqual(sorted(graded_tools(case) - allowed - mocked), [])
                self.assertEqual(sorted(tool for tool in allowed if tool.startswith("mcp__")), [],
                                 "a mocked tool is allowed without being listed")

    def test_the_orchestrator_never_graders_read_the_orchestrator_s_events_only(self):
        """`no-edit` and `no-write` of a manager case: a trace pattern that an orchestrator's
        own call matches and a subagent's does not (a `tool_used` grader would count both, and a
        fix round's implementer edits). The tool is one the case allows, or the grader would pass
        for nothing; so it would on a trace of another shape, which the third grader catches."""
        quoted = '{"type":"tool_use","id":"toolu_2","name":"%s","input":{}}'
        for folder, case in self.cases.items():
            if not folder.startswith("manager-run/"):
                continue
            graders = {grader["name"]: grader for grader in case["graders"]}
            allowed = case["execution"].get("allowed_tools", [])
            for name, tool in sorted(ORCHESTRATOR_NEVER.items()):
                with self.subTest(case=folder, grader=name):
                    grader = dict(graders[name])
                    self.assertEqual(grader.pop("pattern"), ORCHESTRATOR_CALL % tool)
                    self.assertEqual(grader, {"name": name, "type": "regex", "target": "trace",
                                              "flags": "m", "match": "not_contains",
                                              "arm": "both"})
                    self.assertIn(tool, allowed)
                    self.assertIn("Agent", allowed)
            seen = dict(graders["trace-shows-the-orchestrator"])
            self.assertEqual(seen.pop("pattern"), ORCHESTRATOR_CALL % "Agent")
            self.assertEqual(seen, {"name": "trace-shows-the-orchestrator", "type": "regex",
                                    "target": "trace", "flags": "m"})
            self.assertFalse(any(grader["type"] == "tool_used" and grader["tool"] in ("Edit",
                                                                                     "Write")
                                 for grader in case["graders"]), folder)
        for tool in ("Edit", "Write", "Agent"):
            found = re.compile(ORCHESTRATOR_CALL % tool, re.M).search
            dispatch = tool_use("Agent", {"subagent_type": "manager-plugin:implementer",
                                          "prompt": "Use %s. %s" % (tool, quoted % tool)})
            others = [
                trace_event("system", None, "the subagent called %s: %s" % (tool, quoted % tool)),
                trace_event("assistant", "toolu_1", [tool_use(tool, {"file_path": "greet.sh"})]),
                trace_event("user", "toolu_1", [{"type": "tool_result", "tool_use_id": "toolu_1",
                                                 "content": "done"}]),
                trace_event("user", None, [{"type": "tool_result", "tool_use_id": "toolu_1",
                                            "content": quoted % tool}]),
                trace_event("assistant", None, [{"type": "text", "text": quoted % tool},
                                                tool_use("Read", {"file_path": "%s.md" % tool})]),
            ]
            if tool != "Agent":
                others.append(trace_event("assistant", None, [dispatch]))
            own = trace_event("assistant", None, [{"type": "text", "text": "Next."},
                                                  tool_use(tool, {"file_path": "greet.sh"})])
            with self.subTest(tool=tool):
                self.assertIsNone(found(trace_text(others)))
                for place in range(len(others) + 1):
                    self.assertIsNotNone(found(trace_text(others[:place] + [own]
                                                          + others[place:])), place)

    def test_the_retro_switch_grader_reads_the_orchestrator_s_own_bash_call(self):
        """`retro-switch-read` of a manager case: step 0 has the orchestrator run the retro
        switch's script in a Bash call of its own. The pattern finds that call whatever else the
        command and the call hold, and nothing else: not a subagent's call, a Read of the
        script, the script named in another field of a Bash call, or a quoted call."""
        found = []
        for folder, case in self.cases.items():
            for grader in case["graders"]:
                if grader["name"] == "retro-switch-read":
                    found.append(folder)
                    self.assertEqual(grader, {"name": "retro-switch-read", "type": "regex",
                                              "target": "trace", "flags": "m",
                                              "match": "contains", "pattern": RETRO_CALL})
                    self.assertIn("Bash", case["execution"].get("allowed_tools", []))
        self.assertEqual(found, RETRO_CASES)
        script = "/plugins/manager-plugin/skills/manager/scripts/retro.sh"
        step_0 = ('sh "%s"\ngrep \'"version"\' "/plugins/manager-plugin/.claude-plugin/'
                  'plugin.json"\nls "/plugins/manager-plugin/skills/manager/references"' % script)
        quoted = ('{"type":"tool_use","id":"toolu_2","name":"Bash","input":{"command":"sh %s"}}'
                  % script)
        own = [tool_use("Bash", {"command": step_0, "description": "Read the retro switch"}),
               tool_use("Bash", {"description": 'Step 0 {item 1}: the "switch"',
                                 "command": "sh %s; git fetch origin" % script}),
               tool_use("Bash", {"timeout": 5000, "run_in_background": False,
                                 "command": 'd="/a b/manager"; sh "$d/scripts/retro.sh"'})]
        others = [
            trace_event("system", None, "the subagent ran the switch: %s" % quoted),
            trace_event("assistant", "toolu_1", [own[0]]),
            trace_event("user", "toolu_1", [{"type": "tool_result", "tool_use_id": "toolu_1",
                                             "content": "off (no flag file)"}]),
            trace_event("user", None, [{"type": "tool_result", "tool_use_id": "toolu_1",
                                        "content": quoted}]),
            trace_event("assistant", None, [{"type": "text", "text": quoted},
                                            tool_use("Read", {"file_path": script}),
                                            tool_use("Bash", {"command": "git fetch origin",
                                                              "description": "before retro.sh"}),
                                            tool_use("Grep", {"pattern": "retro.sh"})]),
            trace_event("assistant", None, [tool_use("Agent", {
                "subagent_type": "manager-plugin:reviewer",
                "prompt": "Do not run retro.sh: %s" % quoted})]),
        ]
        search = re.compile(RETRO_CALL, re.M).search
        self.assertIsNone(search(trace_text(others)))
        for call in own:
            event = trace_event("assistant", None, [{"type": "text", "text": "Step 0."}, call])
            for place in range(len(others) + 1):
                with self.subTest(command=call["input"]["command"], place=place):
                    self.assertIsNotNone(search(trace_text(others[:place] + [event]
                                                           + others[place:])))

    def test_a_file_grader_has_a_tool_that_can_write(self):
        for folder, case in self.cases.items():
            if any(grader["type"] == "file_exists" and grader.get("exists", True)
                   for grader in case["graders"]):
                with self.subTest(case=folder):
                    self.assertTrue({"Write", "Edit", "Bash"}
                                    & set(case["execution"].get("allowed_tools", [])))

    def test_mocks(self):
        for folder in self.cases:
            responders, listings = mocks(folder)
            for server, tools in responders.items():
                self.assertRegex(server, SEGMENT)
                for tool, (path, front, body) in tools.items():
                    with self.subTest(case=folder, mock="%s/%s" % (server, tool)):
                        self.assertRegex(tool, SEGMENT)
                        self.assertEqual([key for key in front if key not in MOCK_KEYS], [])
                        self.assertEqual(front.get("type", "fixed"), "fixed")
                        self.assertTrue(body.strip())
                        self.assertFalse(any(line in body for line in TEMPLATE_LINES))
                        self.assertIn(tool, listings.get(server, {}), "no _tools.json entry")
                        schema = listings[server][tool].get("inputSchema", {})
                        self.assertEqual(schema.get("type"), "object")
                        self.assertTrue(set(schema.get("required", []))
                                        <= set(schema.get("properties", {})))
                        files = FILE_TEMPLATE.findall(body)
                        if not files and body.lstrip()[:1] in ("{", "["):
                            json.loads(body)
                        for name in files:
                            self.fixtures_exist(os.path.dirname(path), name, schema)

    def fixtures_exist(self, folder, name, schema):
        """A `{{file:...}}` answer has its file for every value the tool's schema allows in the
        `{input.<field>}` parts of the path, inside the responder's folder, holding JSON."""
        fields = re.findall(r"\{input\.([A-Za-z0-9_.-]+)\}", name)
        self.assertLessEqual(len(fields), 1, name)
        values = [None]
        if fields:
            self.assertIn(fields[0], schema.get("required", []))
            values = schema["properties"][fields[0]].get("enum")
            self.assertTrue(values, "%s: no enum to take the file names from" % fields[0])
        for item in values:
            path = name if item is None else name.replace("{input.%s}" % fields[0], item)
            self.assertNotIn("..", path.split("/"))
            self.assertTrue(os.path.isfile(os.path.join(folder, path)), path)
            json.loads(read(os.path.join(folder, path)))

    def test_the_github_stand_in_has_the_tools_the_manager_maps(self):
        """The stand-in is named as the plugin's agents name the server (`mcp__github__...`) and
        mocks only tools `github-backends.md` gives an operation for."""
        mapped = set(re.findall(r"`([a-z_]+)`", read(BACKENDS)))
        tools = set()
        for folder in self.cases:
            responders = mocks(folder)[0]
            self.assertLessEqual(set(responders), {"github"})
            tools.update(responders.get("github", {}))
        self.assertEqual(sorted(tools - mapped), [])
        self.assertLessEqual({"list_pull_requests", "pull_request_read", "merge_pull_request",
                              "add_issue_comment"}, tools)


@unittest.skipUnless(portability.bash() and shutil.which("git"),
                     "needs bash (Git Bash on Windows, not System32's WSL bash) and git")
class ScaffoldTest(unittest.TestCase):
    """The scaffolded workspaces: built the same every time, and the ones the mocks and graders
    of their case describe."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.addClassCleanup(portability.rmtree, cls.tmp)
        cls.cases = {folder: load(folder) for folder in case_folders()
                     if load(folder).get("context", {}).get("scaffold_script")}
        cls.work = {folder: scaffold(folder, os.path.join(cls.tmp, str(number)))
                    for number, folder in enumerate(cls.cases)}

    def text_of(self, folder):
        """Everything a case's graders and mocks say, as one text."""
        case_files = tree(os.path.join(HERE, *folder.split("/")))
        parts = [text for path, text in case_files.items() if path.startswith(("graders/",
                                                                                "mocks/"))]
        responders = mocks(folder)[0]
        return "\n".join(parts + [body for tools in responders.values()
                                  for _, _, body in tools.values()])

    def pull(self, folder):
        """(the pull request the stand-in shows, the bodies of its comments)."""
        folder_path = os.path.join(HERE, *(folder.split("/") + ["mocks", "github"]))
        comments = json.loads(read(os.path.join(folder_path, "pull-get_comments.json")))
        return (json.loads(read(os.path.join(folder_path, "pull-get.json"))),
                [comment["body"] for comment in comments])

    def test_the_cases_with_a_scaffold(self):
        self.assertEqual(sorted(folder.split("/")[-1] for folder in self.cases),
                         sorted(CANDIDATE_PASSES))
        for folder, case in self.cases.items():
            script = case["context"]["scaffold_script"]
            self.assertFalse(os.path.isabs(script) or ".." in script.split("/"), script)

    def test_a_scaffold_builds_the_same_commits_every_time(self):
        for number, folder in enumerate(self.cases):
            again = scaffold(folder, os.path.join(self.tmp, "again%d" % number))
            with self.subTest(case=folder):
                self.assertEqual(git(again, "rev-parse", "HEAD"),
                                 git(self.work[folder], "rev-parse", "HEAD"))

    def test_a_scaffold_refuses_a_folder_that_holds_a_repository(self):
        """Run by hand in a checkout, it must not commit there."""
        for folder, work in self.work.items():
            head = git(work, "rev-parse", "HEAD")
            code, err = run_scaffold(folder, work)
            with self.subTest(case=folder):
                self.assertEqual((code, err), (1, "fixture: this directory already holds a "
                                                  "repository or a fixture file\n"))
                self.assertEqual(git(work, "rev-parse", "HEAD"), head)
                self.assertEqual(git(work, "status", "--porcelain", "--ignored")[1], "")

    def test_the_workspace_is_the_candidate_with_a_clean_tree(self):
        """The eval sandbox (2.1.330, Linux) keeps the run's shell from writing under `.git`:
        no fetch, switch or commit works in a run. So the scaffold leaves what a review needs
        in place: the checkout on the pull request's head, both branches already fetched."""
        for folder, work in self.work.items():
            pull, _ = self.pull(folder)
            head = git(work, "rev-parse", "HEAD")[1]
            with self.subTest(case=folder):
                self.assertEqual(git(work, "status", "--porcelain", "--ignored")[1], "")
                self.assertEqual(pull["head"]["sha"], head)
                self.assertEqual(git(work, "rev-parse", "origin/" + pull["head"]["ref"])[1], head)
                self.assertEqual(git(work, "rev-parse", "origin/" + pull["base"]["ref"])[1],
                                 pull["base"]["sha"])
                self.assertEqual(git(work, "symbolic-ref", "refs/remotes/origin/HEAD")[1],
                                 "refs/remotes/origin/" + pull["base"]["ref"])
                self.assertEqual(git(work, "merge-base", "--is-ancestor", pull["base"]["sha"],
                                     head)[0], 0)

    def test_every_sha_a_case_names_is_a_commit_of_its_workspace(self):
        for folder, work in self.work.items():
            named = sorted(set(SHA.findall(self.text_of(folder))))
            self.assertTrue(named, folder)
            for sha in named:
                with self.subTest(case=folder, sha=sha):
                    self.assertEqual(git(work, "cat-file", "-e", sha + "^{commit}", ok=(0, 1,
                                                                                       128))[0], 0)

    def test_the_candidate_passes_or_fails_the_project_validation_as_the_case_needs(self):
        for folder, work in self.work.items():
            done = subprocess.run(["sh", "test.sh"], cwd=work, capture_output=True)
            with self.subTest(case=folder):
                self.assertEqual(done.returncode == 0, CANDIDATE_PASSES[folder.split("/")[-1]],
                                 done.stdout.decode("utf-8", "replace"))
                self.assertEqual(git(work, "status", "--porcelain", "--ignored")[1], "")

    def test_the_plan_is_a_living_plan_with_a_standing_model_strategy(self):
        """So a run starts without a question: `plan.py check` accepts the plan as on the default
        branch, a standing strategy is recorded and the rules decline the vault and the map."""
        for folder, work in self.work.items():
            plan = git(work, "show", "origin/main:docs/LIVING_PLAN.md")[1] + "\n"
            done = subprocess.run([sys.executable, PLAN_PY, "check"], input=plan.encode("utf-8"),
                                  capture_output=True,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            with self.subTest(case=folder):
                self.assertEqual((done.returncode, done.stdout.decode("utf-8")),
                                 (0, "ok: 1 phase\n"))
                self.assertRegex(plan, r"(?m)^Model strategy: .* scope: standing .* owner: \"")
                # no improvement-pass suffix (absent = off): an eval run starts no Opus pass
                self.assertNotIn("improvement pass: on", plan)
                self.assertRegex(plan, r"(?m)^Status: todo$")
                self.assertIn("No vault and no code map",
                              git(work, "show", "origin/main:CLAUDE.md")[1])

    def test_the_ledger_a_case_starts_from(self):
        """review-before-pinned-merge: one PASS at the candidate, from an earlier run, which is no
        reason to skip the review. fix-round-brake: as many CHANGES REQUIRED lines as the plan
        allows fix rounds, each at an earlier commit of the branch, none at the candidate."""
        line = re.compile(r"review-ledger R[0-9-]+ round ([0-9]+): (PASS|CHANGES REQUIRED) at "
                          r"([0-9a-f]{40}); blockers: (.+)$")
        for folder, work in self.work.items():
            found = [line.match(body) for body in self.pull(folder)[1]]
            self.assertTrue(all(found), folder)
            head = git(work, "rev-parse", "HEAD")[1]
            plan = git(work, "show", "origin/main:docs/LIVING_PLAN.md")[1]
            limit = int(re.search(r"(?m)^Fix-round limit per phase: ([0-9]+)$", plan).group(1))
            with self.subTest(case=folder):
                self.assertEqual([int(match.group(1)) for match in found],
                                 list(range(1, len(found) + 1)))
                if CANDIDATE_PASSES[folder.split("/")[-1]]:
                    self.assertEqual([match.group(2, 3, 4) for match in found],
                                     [("PASS", head, "none")])
                    continue
                self.assertEqual([match.group(2) for match in found], ["CHANGES REQUIRED"] * limit)
                branch = git(work, "rev-list", "--reverse", "origin/main..HEAD")[1].split()
                self.assertEqual([match.group(3) for match in found], branch[:-1])
                titles = [match.group(4) for match in found]
                self.assertEqual(len(set(titles)), len(titles))


class ReadmeTest(unittest.TestCase):
    """The repository's README says how the cases are run; an installed copy has no README."""

    def setUp(self):
        if not os.path.isfile(README):
            self.skipTest("no README.md beside this plugin copy")
        self.text = " ".join(read(README).split())

    def test_the_run_command_and_the_cases(self):
        tools = set()
        for folder in case_folders():
            case = load(folder)
            self.assertTrue("`%s`" % case["name"] in self.text, "not named: " + case["name"])
            tools.update(tool for tool in case["execution"].get("allowed_tools", []))
        command = re.search(r"claude plugin eval plugins/manager-plugin [^`]*", self.text)
        self.assertTrue(command, "no run command")
        for flag in ("--scaffold", "--ablation none", "--no-publish", "--allow-tools"):
            self.assertIn(flag, command.group(0))
        granted = set(command.group(0).split("--allow-tools")[1].split("--")[0].split())
        self.assertEqual(sorted(tools - granted - {"Read", "Glob", "Grep", "Skill"}), [],
                         "a tool a case allows needs the operator's grant")
        self.assertTrue("python3 -m unittest discover -s plugins/manager-plugin/evals" in self.text,
                        "the README does not give this test's command")


if __name__ == "__main__":
    unittest.main()
