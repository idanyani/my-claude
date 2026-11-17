---
max_turns: 5
allowed_tools: [Skill, Read, Glob, Grep]
---

File an issue: a code review of fetcher.py said the retry loop might never stop if a host times out ten times in a row. Nobody has seen that happen, and we don't know whether it does.
