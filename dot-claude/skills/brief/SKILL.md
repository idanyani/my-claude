---
name: brief
description: Use when the user needs filling in on a session's work so they can review or steer it -- says "brief", "/brief", "bring me up to speed", "where are we", "I lost track", "remind me what we were solving", or "re-ask your questions" -- and whenever work is reported for review or a decision needs background the user may not hold. Do NOT use for a quick question that stands on its own (ask it directly), commit messages, PR bodies, or docs.
---

# Brief the user

The reader is a reviewer who trusts the work and checks it: they confirm or reject the claims it
rests on, refocus it, and make the decisions it needs. They may have been away for days and hold
none of the session in their head. A brief lets them do all of that from one screen, without
asking for a re-explanation.

## Gather

Take the links from GitHub, not from memory of the session, so they are current even for an old
issue. Skip what the session already loaded this turn, and the step altogether for a session with
no GitHub issue:

- `gh issue view <N> --json number,title,body,state,comments` -- the issue the session works on.
- `gh api repos/{owner}/{repo}/issues/<N>/timeline --paginate -q '.[] | select(.event ==
  "cross-referenced") | .source.issue | "\(.repository.full_name)#\(.number) \(.title)"'` --
  what refers to it, from any repo: its PRs, and the epic (an issue whose title starts `Epic:`)
  that lists it. Name a link in another repo as `<repo>#<N>`.

## Format

```
<repo>@<branch>: the state now, and what waits on the user, if anything.

Context    The links the reader needs, top-down, a few words each: epic --> issue --> PR.
Progress   Done / in progress / blocked on what.
Findings   1. <claim> [checked: <evidence>] / [inferred: <from what>] / [assumed]
My calls   1. <choice made without the user>: one-line reason.
Your turn  1. <decision>: the options and what each leads to; the recommendation.
```

- **Headline:** the user tracks work by issue, and an issue's branch names it with a short
  summary (`42-retry-uploads`). State what waits on the user by what it blocks ("one decision
  blocks the merge"), or that nothing does.
- **Context:** only the links that explain the rest. Leave out the epic when the issue stands on
  its own.
- **Findings:** only claims that change the picture. The tag tells the reviewer where to look:
  `checked` names its evidence (a test, a log line, a source), `inferred` names what it rests on,
  `assumed` asks the user to confirm.
- **My calls:** every design choice made without the user, so they catch the ones they would
  reject before work builds on them.
- **Your turn:** each question stands on its own: what is being decided, why it matters, the
  options, the recommendation. Numbered, so the user can answer by number.

## Rules

- Read linearly: each line uses only terms introduced above it, never a forward reference.
- Every `#N`, file, or term gets a few words the first time it appears, or is left out. Give
  background only where the reader needs it to follow the rest.
- Each fact once. Leave out an empty section.
- One screen. Details only when the user asks for them.
