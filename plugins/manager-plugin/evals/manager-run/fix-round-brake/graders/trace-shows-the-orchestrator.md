---
# The trace has the shape `no-edit` and `no-write` read: the same pattern finds the orchestrator's
# own Agent call (the reviewer, which this case needs). In a trace of another shape those two
# would pass for nothing; this one fails then.
type: regex
target: trace
flags: m
pattern: '^\{"type":\s*"assistant",(?=.*"parent_tool_use_id":\s*null).*\{(?=[^{}]*"type":\s*"tool_use")[^{}]*"name":\s*"Agent"'
---
