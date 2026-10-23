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
[references/git-workflow.md](references/git-workflow.md); read it before Phase 4, since the phases
that branch, open, review, and merge the PR follow its steps. The helper scripts live in this skill's
`scripts/` directory and are invoked as plain files: `python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py`
(stdlib-only; they need just `python3`, `git`, and `gh` on PATH and run against the current
working directory's repo).

## Phase 1 -- Ground yourself in the project

Read context proportional to the issue, always including `README.md` (the canonical project
description) and recent commit subjects (`git log --oneline -10`) -- the issue may already be
addressed, superseded, or in tension with fresh changes. `git show <sha>` only when a subject
looks related. Read the repo docs relevant to the issue's area (the repo's `CLAUDE.md` and
`docs/` index point to them).

## Phase 2 -- Read the issue

`python3 ${CLAUDE_SKILL_DIR}/scripts/view_issue.py <number>` (parse the number from `$ARGUMENTS`).
Restate the issue in a sentence or two and pin the acceptance criteria; if it is vague or
criteria-less, ask the user before proceeding.

## Phase 3 -- Check for duplicates and prior art

- `gh issue list --search "<key terms>" --state all` -- duplicate issues.
- `gh pr list --search "<key terms>" --state all` -- existing or merged PRs.

If a duplicate or in-flight PR exists, stop and surface it -- do not start parallel work.

## Phase 4 -- Set up an isolated workspace

Unless `--in-place` was given or the session is already in a worktree, call
`EnterWorktree(name="<number>-<kebab-summary>")`. Then branch as step 1 of the workflow doc says. To resolve several issues in parallel, spawn one
subagent per issue with `isolation: "worktree"`.

## Phase 5 -- Implement test-first

Follow CLAUDE.md's TDD rules; a failing test must fail for the right reason. Test behavior and
contracts, not implementation detail.

## Phase 6 -- Run the test pipeline

Run the repo's test pipeline (named in its `docs/git-workflow.md` stub or `CLAUDE.md`) and paste
real output.

## Phase 7 -- Simplify

Once the pipeline passes, run the bundled `/simplify` on the uncommitted change, so its cleanup
fixes land in the implementation commit rather than as review fix-ups. First `git add -N` any new
files: its diff leaves untracked files out. Skip it when the change has no code outside tests --
prose (docs, skills, `CLAUDE.md`) and test-only changes give its cleanup angles nothing to work
on. If it edited anything, revert any edit that weakens a test, run the pipeline again, and paste
that output too; revert the edits that turn it red rather than fixing forward.

## Phase 8 -- Commit

One commit for the implementation, message in the repo's commit style, ending with
`Resolves #<number>`. The body becomes the PR description, so it states the chosen solution and
the rejected alternatives with why; the problem stays in the issue.

## Phase 9 -- Open the PR

Open the PR as step 2 of the workflow doc says.

## Phase 10 -- Review the PR

Run the review that opens step 3 of the workflow doc.

## Phase 11 -- Address the review

Handle the review's findings as the rest of step 3 of the workflow doc says.

## Phase 12 -- Arm auto-merge

Run `finish_branch.py` as step 4 of the workflow doc says.

## Phase 13 -- Exit the worktree

Leave the worktree as the end of step 4 of the workflow doc says.

## Phase 14 -- Report to the user

Summarize the change, the test results, the review triage, and the PR link for the user.
