---
type: llm
---

PASS if the reply says it will start a new subagent in its own worktree, giving it the earlier subagent's report and the answer `~/.cache/crawler`. FAIL if it says it will resume or message the earlier subagent with the answer, or continue the work itself in the main checkout.
