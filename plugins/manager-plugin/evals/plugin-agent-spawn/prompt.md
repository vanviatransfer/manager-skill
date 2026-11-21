---
description: A delegated task that changes files goes to a plugin agent, not to general-purpose
tags: [general-purpose-spawn]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Agent, Read, Glob, Grep, Write, Edit]
---
Hand this to a subagent instead of doing it yourself: create `docs/primes.md` holding the prime
numbers below 60, one per line, smallest first, and nothing else. When the subagent is done, read
the file and tell me whether it is right.
