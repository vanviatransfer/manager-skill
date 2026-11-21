---
# No merge call is without that pin, or pinned to another commit.
type: regex
target: mock_calls
match: not_contains
pattern: '"tool":\s*"mcp__github__merge_pull_request"(?![^\n]*"expectedHeadSha":\s*"9a24685e4a99c146f2f8b171b7026aac7a93c01f")'
---
