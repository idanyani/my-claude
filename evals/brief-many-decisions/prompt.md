---
max_turns: 10
allowed_tools: [Skill, Read, Glob, Grep]
---

Where are we? I lost track. My notes from the last few days:

- repo crawler, branch 41-slow-hosts, PR #44 open, CI green
- issue #41: a slow host holds up the whole nightly crawl, so it misses its 6am deadline
- PR #44 adds a per-host time budget: a host that uses 10 minutes is skipped for the night
- earlier we agreed on "per-host order" (fetch hosts in turn rather than one host's pages in a row) -- not built yet
- open: budget 10 min or 20 min? 10 min skipped 3 hosts last night
- open: build "per-host order" in this PR or the next?
- open: should a skipped host be retried first the next night?
- open: alert someone when more than 5 hosts are skipped?
- earlier we named the old crawl mode "level by level" (all pages one link from the start page, then all pages two links away, and so on)
- open: keep the old "level by level" crawl mode as a fallback, or delete it?
- open: rename the budget setting from host_budget to host_time_budget_s?
