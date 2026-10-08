# Git Workflow

Every change reaches `main` the same way: a short-lived branch, a pull request, and a
squash-merge once CI passes. This is the canonical workflow doc; each consuming repo's
`docs/git-workflow.md` stub links here instead of repeating it, and holds only the
repo-specifics (what `verify` runs, where its CI workflow lives).

The helper scripts live in this skill's `scripts/` directory and are invoked as plain files:
`python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py`. They are stdlib-only and need just `python3`, `git`,
and `gh` on PATH; they run against the current working directory's repo.

## Background

- **Pull request (PR):** a request to merge a branch into `main`. GitHub runs CI on it and
  shows reviews before it merges.
- **`verify`:** the project's CI check -- what it runs is repo-specific and named in the
  repo's `docs/git-workflow.md` stub or `CLAUDE.md`. It is the one *required* check: branch
  protection refuses to merge until it passes. Branch protection leaves "require branches to be
  up to date" off: auto-merge never updates a branch, so with it on, every open PR stalls once
  another merges.
- **Auto-merge:** GitHub merges the PR by itself once `verify` passes, so you do not watch
  the run.
- **Review:** an in-session `/code-review <pr>` run before arming auto-merge. It is
  *advisory* -- it never gates the merge; you read the findings and decide, and `verify` is
  the only gate.

## Steps

1. **Branch from `main`.** `python3 ${CLAUDE_SKILL_DIR}/scripts/start_branch.py <number>
   <kebab-summary>` (add `--worktree` for a sibling worktree; the script prints the
   dependency-install command the fresh worktree needs). It refuses a dirty tree (it never
   stashes silently -- surface that and ask), prunes `[gone]` branches, then branches from a
   freshly pulled `main`. Never push to `main` directly -- branch protection rejects it for
   everyone, administrators included.
2. **Open the PR.** `git push -u origin <branch>`, then `gh pr create --fill`.
3. **Review the PR.** Run `/code-review <pr>` in this session. Apply the findings worth
   applying and push any fixes **as new commits -- the branch is already pushed and under
   review, so never amend, rebase, or force-push it; the squash-merge in step 4 collapses every
   commit into one on `main`, so branch commit count does not matter.** Dismiss the rest with a
   one-line reason. Review once -- do not loop on further advisory findings; record any
   leftover suggestion as a follow-up issue.
4. **Merge.** Once the commit is final, `gh pr merge --auto --squash --delete-branch`.
   Squash is what collapses the branch's commits into a single commit on `main` -- that is the
   guarantee, so the branch itself may carry several commits (initial work plus review fixes).
   Arming auto-merge is what authorizes the
   merge, so do it only after addressing the review -- never before. GitHub then merges the
   moment `verify` is green (immediately, if it already is) and notifies you; you do not
   watch the run yourself.
5. **Return to `main` and clean up.** `python3 ${CLAUDE_SKILL_DIR}/scripts/finish_branch.py <pr>`
   waits for the merge, then syncs `main` and deletes the local branch (with `--worktree`,
   it first removes the sibling worktree). When the PR cannot merge until you act, it stops
   and says why (see Troubleshooting). Launch it with the Bash tool's `run_in_background`: its
   wait outlasts the tool's 120-second foreground default, which would kill it before the
   cleanup. The harness reports its exit, so do not poll for it. To skip the wait, just
   `git checkout main` and let the merge land asynchronously -- the next `start_branch` deletes
   the `[gone]` branch.

Pause for explicit approval before pushing risky or ambiguous changes. Commit-message
conventions live in the repo's `CLAUDE.md`.

## Troubleshooting

- **PR will not merge -- "no checks reported."** A push can land without firing CI, so no
  `verify` run attaches and auto-merge cannot arm. Close and reopen the PR to re-fire CI.
- **`finish_branch.py` exits 3.** The PR cannot merge until you act; the message says why.
  Fix that, then re-run `finish_branch.py`:
  - *Conflict with `main`:* another PR changed the same lines. Merge `main` into the branch,
    resolve, and push a new commit (never rebase or force-push).
  - *A required check failed:* push a fix as a new commit, or re-run the check if it was flaky.
  - *Auto-merge not armed:* arm it (step 4).
  - *Behind `main`:* the repo requires branches to be up to date (see Background). Run
    `gh pr update-branch <pr>` (it merges `main` in, never rebases), and turn that requirement off.
