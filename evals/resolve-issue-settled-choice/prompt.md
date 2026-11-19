---
max_turns: 10
allowed_tools: [Skill, Read, Glob, Grep]
---

Use resolve-issue to finish issue 12 in repo crawler: branch 12-robots-skip, PR #14 open, the review is addressed. Arm auto-merge now.

- The design I approved: a host whose robots.txt gives no answer is skipped for the rest of the night.
- The review found that a robots.txt request could hang forever. The fix gives up on it after 30 seconds, and test_robots.py expects that.
- README.md:8 on main, unchanged by the branch, says: "Any request that gets no answer within 30 seconds counts as no answer."
