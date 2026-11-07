---
name: file-issue
description: Use when a problem is to be recorded as a GitHub issue -- the user says "file an issue", "open an issue", "file it", "/file-issue", or work calls for one (a review's follow-up, a leftover suggestion, the issue a change to `main` resolves). Do NOT use for implementing an issue (use resolve-issue).
---

# File a GitHub issue

Arguments: `$ARGUMENTS` -- the problem to record, and optionally the repo (`owner/name`); the
default is the current checkout's repo.

## Step 1 -- Search for an issue that already covers it

Search open and closed issues with the problem's key terms, trying more than one wording, since
whoever filed an earlier issue may have described it differently:
`gh issue list --search "<terms>" --state all`. Read the likely matches with `gh issue view`.

- An open issue covers it: comment the new evidence there, if any, and stop.
- A closed issue covers it: if it was fixed and the problem is back, file a new issue that links
  it; otherwise comment there and stop.

## Step 2 -- Write the issue

An issue states one problem: symptom, impact, evidence -- never the fix. Two problems are two
issues, each resolved by its own PR.

## Step 3 -- File it

`gh issue create --title "<title>" --body "<body>"`, then give the user its number and link and
say what Step 1 searched.
