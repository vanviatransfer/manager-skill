---
# The orchestrator itself runs the retro switch's script (step 0, item 1 of
# `establish-state.md`): an `assistant` event with `"parent_tool_use_id":null` holds a Bash call
# whose command names `retro.sh`. A subagent's call, a Read of the script, and the script named
# in a description or a dispatch do not count.
type: regex
target: trace
flags: m
match: contains
pattern: '^\{"type":\s*"assistant",(?=.*"parent_tool_use_id":\s*null).*\{(?=[^{}]*"type":\s*"tool_use")[^{}]*"name":\s*"Bash"[^{}]*"input":\s*\{(?:[^{}"\\]|"(?:[^"\\]|\\.)*")*?"command":\s*"(?:[^"\\]|\\.)*retro\.sh'
---
