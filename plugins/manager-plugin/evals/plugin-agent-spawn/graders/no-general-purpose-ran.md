---
type: llm
focus: trace
---
No general-purpose subagent did any work in this run. An Agent call whose `subagent_type` is
`general-purpose`, or that has no `subagent_type`, is acceptable only if its tool result is the
refusal from the plugin's hook (it starts with "manager-plugin: general-purpose is blocked here")
and the task was then dispatched again to a `manager-plugin:` agent. Fail if any such call
returned a subagent's result instead of that refusal. Pass if there was no such call at all.
