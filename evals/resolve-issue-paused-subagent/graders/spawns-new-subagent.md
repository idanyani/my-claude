---
type: llm
---

PASS if the reply says it will start a new subagent in its own worktree, whose prompt carries the design the user approved, the earlier subagent's report, the answer `~/.cache/crawler`, and the instruction to stop and return any design choice left open. FAIL if it says it will resume or message the earlier subagent with the answer, continue the work itself in this session (in any worktree or checkout), or leave out the approved design or the answer.
