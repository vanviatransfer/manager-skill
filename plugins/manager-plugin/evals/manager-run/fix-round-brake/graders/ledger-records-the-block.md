---
# The review ledger gets its line for a phase that blocks.
type: regex
target: mock_calls
pattern: '"tool":\s*"mcp__github__add_issue_comment"[^\n]*review-ledger R[0-9-]+ blocked:'
---
