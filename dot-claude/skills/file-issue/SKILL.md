---
name: file-issue
description: Use when a problem is to be recorded as a GitHub issue -- the user says "file an issue", "open an issue", "/file-issue", or agrees to an offer to file one, or work calls for one (a review finding the user picked, the issue a change to `main` resolves). Do NOT use for implementing an issue (use resolve-issue).
---

# File a GitHub issue

Arguments: `$ARGUMENTS` -- the problem to record, in the current checkout's repo.

## Step 1 -- Search for an issue that already covers it

Search open and closed issues with the problem's key terms, trying more than one wording, since
whoever filed an earlier issue may have described it differently:
`gh issue list --search "<terms>" --state all`. Read each likely match with
`gh issue view <N> --json number,title,body,state,stateReason,comments` (a bare `gh issue view`
fails on repos hit by the Projects-classic deprecation).

- An open issue covers it: comment the new evidence there, if any, and skip to Step 4.
- A closed issue covers it: if it was closed as a duplicate, follow it to the issue it
  duplicates. If it was fixed and the problem is back, or closed as not planned and now in
  scope, file a new issue that links it. Otherwise comment the new evidence there and skip to
  Step 4.

## Step 2 -- Write the issue

An issue states one problem: symptom, impact, evidence -- never the fix. Two problems are two
issues, each resolved by its own PR.

Evidence, in an issue or in a comment on one, shows the problem exists: for a failure, a run that
showed it -- a failing test, a log line, a measurement; for anything else, where to see it, such
as a `file:line`. A failure no run has shown is not an issue yet: file nothing, and name the run
that would show it -- the logs to read, the test to write.

A number, in the issue or in a comment on one, is measured or cited, and says by what: an
estimate reads as a fact and misleads until someone measures.

## Step 3 -- File it

Label the issue with where its work came from, judged from the conversation, since every issue
an agent files has the same author:

- `origin:developer` -- the developer brought the problem: they described it, or asked for the
  work it blocks.
- `origin:proposed` -- an agent proposed it, and the developer picked or approved it, as when
  they choose findings from a report.
- `origin:agent` -- an agent files it without the developer asking for it, as a session does
  for a problem it raised itself.

Write the body to a file outside the repo (the session's scratchpad, or a `mktemp` file), so
the shell never reads its backticks and `$`, and pass it by path. The first command makes sure
the label exists in the repo:

```sh
gh label create <origin> --force
gh issue create --title "<title>" --body-file <file> --label <origin>
```

## Step 4 -- Report

Give the issue's number and link -- the one filed or the one that already covered it, with
whether you commented -- and its origin label, and say what Step 1 searched. For a failure no run has shown, say that
nothing was filed, and name the run that would show it.
