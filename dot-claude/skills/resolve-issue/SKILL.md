---
name: resolve-issue
description: Use when the user wants a GitHub issue implemented end-to-end -- says "resolve issue N", "/resolve-issue N", "start issue N", "work on issue N", or pastes a GitHub issue URL. Do NOT use for reviewing an existing PR (use /code-review) or for issue triage without implementation.
allowed-tools:
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/view_issue.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/start_branch.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/open_pr.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/finish_branch.py *)
  - EnterWorktree
  - ExitWorktree
---

# Resolve a GitHub Issue

Arguments: `$ARGUMENTS` -- an issue number (e.g. `42`) or full issue URL, optionally followed by
`--in-place` to branch in the main checkout instead of an isolated worktree. If empty, run
`gh issue list --state open`, show the list, and ask the user which issue to work on.

This skill is repo-agnostic. The repo's `CLAUDE.md` is the law (TDD rules, commit style, naming);
repo-specifics such as what `verify` runs live in the repo's `docs/git-workflow.md` stub -- read
both. The branch-and-PR mechanics are documented once in this skill's workflow doc,
[references/git-workflow.md](references/git-workflow.md); read it before Phase 5, since the phases
that branch, open, review, and merge the PR follow its steps. The helper scripts live in this skill's
`scripts/` directory and are invoked as plain files: `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py`
(stdlib-only; they need just `python3`, `git`, and `gh` on PATH and run against the current
working directory's repo).

## Phase 1 -- Ground yourself in the project

Read context proportional to the issue, always including `README.md` (the canonical project
description) and recent commit subjects (`git log --oneline -10`) -- the issue may already be
addressed, superseded, or in tension with fresh changes. `git show <sha>` only when a subject
looks related. Read the repo docs relevant to the issue's area (the repo's `CLAUDE.md` and
`docs/` index point to them), and the decision records in `docs/decisions/` on the issue's
area. A design the issue needs that a record rejects goes in Phase 4's brief as a "Chose" line,
with whether the record's reason still holds.

## Phase 2 -- Read the issue

`python3 ${CLAUDE_SKILL_DIR}/scripts/view_issue.py <number>` (parse the number from `$ARGUMENTS`).
Pin the acceptance criteria.

## Phase 3 -- Check for duplicates and prior art

- `gh issue list --search "<key terms>" --state all` -- duplicate issues.
- `gh pr list --search "<key terms>" --state all` -- existing or merged PRs.

If a duplicate or in-flight PR exists, stop and surface it -- do not start parallel work.

## Phase 4 -- Brief the user

Brief the user on the issue in the brief skill's format, so they can steer before any work
starts. For an issue filed a while ago, say what has happened since: its comments, and the
related PRs and commits Phases 1 and 3 found. For an issue that reports a defect, apply
CLAUDE.md's problem-solving rules before choosing a fix: from reading the code and history, say
what causes it, with the evidence -- or that the cause is unknown, and what was checked -- and
whether the fix removes the cause or works around it; when the defect is in something the repo
built, say whether that thing should exist at all. These are "Chose" lines: a cause is a claim
the user can reject before work builds on it. If the issue is vague or criteria-less, ask in the
brief's Your turn. Wait for the user's answer when the brief has a "Chose" line or Your turn
items, so they can reject a choice before work builds on it; otherwise carry on.

## Phase 5 -- Set up an isolated workspace

Unless `--in-place` was given or the session is already in a worktree, call
`EnterWorktree(name="<number>-<kebab-summary>")`. Then branch as step 1 of the workflow doc says.

To resolve several issues in parallel, spawn one subagent per issue with `isolation: "worktree"`
instead, without entering a worktree here. The user, not this session or the subagent, settles
each design: spawn it only once Phase 4 ran for that issue in this session, its brief stating the
planned design as "Chose" lines, and the user answered. Pass the user's decisions in the prompt
as the answer to the subagent's own Phase 4, and tell it to stop and return any design choice
they leave open, at any phase, review included, rather than make it. Bring that choice to the
user, then continue the subagent with their answer (`SendMessage`).

## Phase 6 -- Implement test-first

Follow CLAUDE.md's TDD rules; a failing test must fail for the right reason. Test behavior and
contracts, not implementation detail. When an approach fails or the user redirects it, go back to
the cause before trying another, and tell the user if it differs from the one the brief named.

## Phase 7 -- Run the test pipeline

Run the repo's test pipeline (named in its `docs/git-workflow.md` stub or `CLAUDE.md`) and paste
real output.

## Phase 8 -- Simplify

Once the pipeline passes, run the bundled `/simplify` on the uncommitted change, so its cleanup
fixes land in the implementation commit rather than as review fix-ups. First `git add -N` each file
the change created: its diff leaves untracked files out. Skip it when the change has no code outside tests --
prose (docs, skills, `CLAUDE.md`) and test-only changes give its cleanup angles nothing to work
on. If it edited anything, revert any edit that weakens a test, run the pipeline again, and paste
that output too; revert the edits that turn it red rather than fixing forward.

## Phase 9 -- Commit

Commit the implementation, message in the repo's commit style, ending with `Resolves #<number>`.
That commit's subject and body become the PR's title and description, so the body states the
chosen solution and the rejected alternatives with why; the problem stays in the issue. The same
commit adds a decision record for each alternative a brief showed the user rejected for a reason
that will still hold, since the next change reads the records, not this commit; a review fix that
adopts a recorded alternative deletes its record.

## Phase 10 -- Open the PR

Open the PR as step 2 of the workflow doc says.

## Phase 11 -- Review the PR

Run the review that opens step 3 of the workflow doc.

## Phase 12 -- Address the review

Handle the review's findings as the rest of step 3 of the workflow doc says.

## Phase 13 -- Arm auto-merge

Run `finish_branch.py` as step 4 of the workflow doc says.

## Phase 14 -- Exit the worktree

Leave the worktree as the end of step 4 of the workflow doc says.

## Phase 15 -- Report to the user

Brief the user on the result in the brief skill's format: What I did says what is different now,
with the test results and the review triage, including the known limits step 3 of the workflow
doc added to the PR. The findings it held go under Your turn as one decision, which to file as
issues: the recorded lines ranked HIGH first, each prefixed with a letter to answer by. File the ones the user picks with `/file-issue`.
