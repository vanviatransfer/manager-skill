---
# The final message is the reviewer's answer, with its verdict line.
type: regex
target: last_message
flags: m
---
^\W*VERDICT: (PASS WITH NOTES|PASS|CHANGES REQUIRED)\b
