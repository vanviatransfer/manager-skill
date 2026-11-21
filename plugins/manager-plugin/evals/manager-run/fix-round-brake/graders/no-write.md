---
# The orchestrator never calls Write. A `tool_used` grader counts the calls of every session
# of the run, a subagent's too (an implementer edits), so this one reads the trace instead: an
# `assistant` event with `"parent_tool_use_id":null` is the orchestrator's own turn.
# `trace-shows-the-orchestrator` holds the same pattern to a call that must be there.
type: regex
target: trace
flags: m
match: not_contains
pattern: '^\{"type":\s*"assistant",(?=.*"parent_tool_use_id":\s*null).*\{(?=[^{}]*"type":\s*"tool_use")[^{}]*"name":\s*"Write"'
arm: both
---
