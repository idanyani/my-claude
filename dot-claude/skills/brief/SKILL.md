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

For a session that works on a GitHub issue, find its PR on GitHub rather than from memory of the
session, so it is current even for an old issue. Skip what the session already loaded this turn:

- `gh issue view <N> --json number,title,body,state,comments` -- the issue the session works on.
- `gh api repos/{owner}/{repo}/issues/<N>/timeline --paginate -q '.[] | select(.event ==
  "cross-referenced") | .source.issue | select(.pull_request) | "\(.repository.full_name)#\(.number) \(.title)"'`
  -- the PR that resolves it, from any repo. Name a PR in another repo as `<repo>#<N>`.

## Format

Write markdown, which the terminal renders: three sections, in this order.

**Where we are**
- **\<repo\>@\<branch\>** (PR #\<N\>)
- Done: \<plain words\>
- Next: \<plain words\>
- Blocked on: \<a blocker outside the user's control: CI, another PR\>

**What to check**
- \<claim\>: checked by \<evidence\> | guessed from \<what\> | assumed, please confirm
- I chose \<X\>: \<one-line reason\>
- Look first at `<file:line>`; verify with `<command>`

**Your turn**
1. \<decision\>? A: \<result\>. B: \<result\>. **I recommend A**: \<reason\>.

For example:

> **Where we are**
> - **my-claude@42-retry-uploads** (PR #45)
> - Done: failed uploads now retry 3 times
> - Next: merge, once you answer below
>
> **What to check**
> - Retries stop on a 4xx error: checked by a new test
> - I chose a fixed 2s wait over a growing one: simpler, and uploads are rare
> - Look first at `upload.py:80`; verify with `uv run pytest -k retry`
>
> **Your turn**
> 1. Also retry on timeout? Yes: fewer failures, slower errors. No: as now. **I recommend
>    yes**: timeouts are the most common failure.

- **Where we are:** the branch names the issue, so it stands in for a link. Add the PR number
  once a PR exists. Blocked on names only what the user cannot answer; a decision of theirs goes
  in Your turn.
- **What to check:** everything the reviewer should confirm or reject. A claim's tag says where
  to look: its evidence (a test, a log line, a source), what it was guessed from, or that it is
  assumed and needs the user's word. List every choice made without the user, so they catch one
  they would reject before work builds on it. End with the few spots worth reading first and a
  command that shows the work runs.
- **Your turn:** always last, so the last thing read is what the user must answer. Each
  decision stands on its own: the question, its options and where each leads, and the
  recommendation. Numbered, so the user can answer by number. With nothing to decide, it is one
  line: `**Your turn:** nothing. Next I'll <X>.`

## Rules

- Plain and short: one idea per bullet, about 15 words at most, everyday words. Describe what a
  function, flag, or script does instead of naming it, unless the user must act on the name.
- Problem before mechanism.
- Bold only the section labels, the branch, and the recommendation; leave a blank line between
  sections.
- Read linearly: each line uses only terms introduced above it, never a forward reference.
- Every `#N`, file, or term gets a few words the first time it appears, or is left out.
- Each fact once. Leave out an empty line or section.
- One screen. Details only when the user asks for them.
