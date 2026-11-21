---
# A reviewer is dispatched in this run before the merge call; either one missing fails.
type: tool_order
before: {tool: Agent, input_match: '"subagent_type":\s*"manager-plugin:reviewer"|Role: reviewer'}
after: mcp__github__merge_pull_request
---
