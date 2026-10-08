---
name: resolve-issue
description: Use when the user wants a GitHub issue implemented end-to-end -- says "resolve issue N", "/resolve-issue N", "start issue N", "work on issue N", or pastes a GitHub issue URL. Do NOT use for reviewing an existing PR (use /code-review) or for issue triage without implementation.
allowed-tools:
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/view_issue.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/start_branch.py *)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/finish_branch.py *)
---

# Resolve a GitHub Issue

Arguments: `$ARGUMENTS` -- an issue number (e.g. `42`) or full issue URL, optionally followed by
`--worktree` to isolate work in a git worktree instead of a branch in place. If empty, run
`gh issue list --state open`, show the list, and ask the user which issue to work on.

This skill is repo-agnostic. The repo's `CLAUDE.md` is the law (TDD rules, commit style, naming);
repo-specifics such as what `verify` runs live in the repo's `docs/git-workflow.md` stub -- read
both. The branch-and-PR mechanics are documented once in this skill's
[references/git-workflow.md](references/git-workflow.md). The helper scripts live in this skill's
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

`python3 ${CLAUDE_SKILL_DIR}/scripts/start_branch.py <number> <short-kebab-summary>` (add `--worktree` to
isolate the work in a sibling worktree instead of branching in place; the script prints the
dependency-install command the fresh worktree needs). If it refuses a dirty tree, surface that
and ask the user -- never stash silently.

## Phase 5 -- Classify and implement

State whether it is a **bug** or **feature**, then follow the repo CLAUDE.md's TDD rules: bugs
reproduce-first (a failing test that fails for the right reason), features skeleton-first. Test
behavior and contracts, not implementation detail.

## Phase 6 -- Verify

Run the repo's test pipeline (named in its `docs/git-workflow.md` stub or `CLAUDE.md`) and paste
real output.

## Phase 7 -- Commit and open an auto-merging PR

One commit for the implementation, message in the repo's commit style, ending with
`Resolves #<number>`. `gh pr create --fill` turns the commit body into the PR description, so
the body states the chosen solution and the rejected alternatives with why -- the problem
stays in the issue. Then: `git push -u origin <branch>`, `gh pr create --fill`, and review it
in this session with `/code-review <pr>`. Apply the findings worth applying and push fixes **as
additional commits -- never amend or force-push the pushed branch; the squash-merge collapses
them into one commit on `main`**; dismiss the rest with a one-line reason. Review once -- do not
loop on further advisory findings. Only then arm auto-merge:
`gh pr merge --auto --squash --delete-branch`.

## Phase 8 -- Finish and clean up

`python3 ${CLAUDE_SKILL_DIR}/scripts/finish_branch.py <pr>` (add `--worktree` if you used it in Phase 4)
waits for the merge, then syncs `main` and deletes the local branch, first removing the sibling
worktree if you used one. Launch it with `run_in_background` -- its wait outlasts the Bash tool's
foreground default -- and wait for its exit notification rather than polling. Then summarize
the change, the test results, the triage, and the PR link for the user.
