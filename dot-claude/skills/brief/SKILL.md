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
  "cross-referenced") | .source.issue | select(.pull_request and (.state == "open" or .pull_request.merged_at)) |
  "\(.repository.full_name)#\(.number) \(.title)"'` -- its open or merged PRs, from any repo;
  pick the one that resolves it.

## Format

Write markdown, which the terminal renders: three sections, in this order.

**Where we are**
- **\<repo\>@\<branch\>** (PR \<ref\>)
- \<the big picture: what the project is for, and the larger plan, if any\>
- \<the problem this issue solves\>

**What I did**
- \<Verb\>ed \<what\>: \<result\>. Checked by \<evidence\> | guessed from \<what\> | assumed,
  please confirm
- Chose \<X\> over \<Y\>: \<one-line reason\>
- Read first: `<file:line>`; verify with `<command>`

**Your turn**
1. \<decision\>? A: \<result\>. B: \<result\>. **I recommend A**: \<reason\>.

For example:

> **Where we are**
> - **my-claude@42-retry-uploads** (PR #45)
> - The app backs up phone photos to the cloud.
> - A failed upload is never tried again, so the photo stays without a backup.
>
> **What I did**
> - Implemented retries: a failed upload now tries 3 more times. Checked by a new test.
> - Found that a 4xx error means the server refuses the photo, so retries stop there. Checked
>   by a new test.
> - Chose a fixed 2s wait over a growing one: simpler, and uploads are rare.
> - Read first: `upload.py:80`; verify with `uv run pytest -k retry`
>
> **Your turn**
> 1. Also retry on timeout? Yes: fewer failures, slower errors. No: as now. **I recommend
>    yes**: timeouts are the most common failure.

- **Where we are:** gets the reader back into the work from the top down: the big picture,
  then the problem at hand, in a few lines. Introduce here the terms the rest of the brief
  uses. An issue branch names the issue, so it stands in for a link. When the branch does not
  name it (still on `main`, or the issue lives in another repo), add the issue as
  `#<N> <a few words>`. Add the PR once one exists: `#<N>`, or `<repo>#<N>` in another repo.
- **What I did:** everything the reviewer should confirm or reject, findings included. Each
  bullet starts with a past-tense verb (Implemented, Scanned, Reviewed, Found) and ends on its
  result, not the steps that led there. The tag says where to look: its evidence (a test, a
  log line, a source), what it was guessed from, or that it is assumed and needs the user's
  word. List every choice made without the user, so they catch one they would reject before
  work builds on it. When a number replaces one the user has seen, give both and why it
  changed. End with the few spots worth reading first and a command that shows the work runs.
- **Your turn:** always last, so the last thing read is what the user must answer. Each
  decision stands on its own: the question, its options and where each leads, and the
  recommendation. Numbered, so the user can answer by number. With nothing to decide, it is one
  line saying what happens next without the user and what it waits on (CI, another PR):
  `**Your turn:** nothing. <next step>, once <what it waits on>.`

## Rules

- Plain and short: one idea per bullet, about 15 words at most (a decision may run longer),
  everyday words. Describe what a
  function, flag, or script does instead of naming it, unless the user must act on the name.
- Problem before mechanism.
- Bold only the section labels, the branch, and the recommendation; leave a blank line between
  sections.
- Read linearly: each line uses only terms introduced above it, never a forward reference.
- Every `#N`, file, or term gets a few words the first time it appears, or is left out. Give
  background only where the reader needs it to follow the rest.
- Each fact once. Leave out an empty line or section.
- One screen. Details only when the user asks for them.
