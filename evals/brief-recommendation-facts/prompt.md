---
max_turns: 10
allowed_tools: [Skill, Read, Glob, Grep]
---

Bring me up to speed, I've been away. Notes:

- repo crawler, branch 52-polite-wait, PR #53 open, CI green
- issue #52: a site blocked us last week for sending requests too fast
- PR #53 adds a wait between two requests to the same site, 1 second for now
- open: keep 1 second or raise it to 5? I remember that other well-known crawlers wait about 5 seconds by default, but I haven't looked it up
- the blocked site's log showed about 3 requests per second from us (checked in its access log)
