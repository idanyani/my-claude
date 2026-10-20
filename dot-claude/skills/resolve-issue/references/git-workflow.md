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

1. **Branch from `main`.** Work in a Claude Code worktree (`EnterWorktree`, subagent
   `isolation: "worktree"`, or `claude --worktree`) unless branching in place on purpose, then
   run `python3 ${CLAUDE_SKILL_DIR}/scripts/start_branch.py <number> <kebab-summary>`. It
   refuses a dirty tree (it never stashes silently -- surface that and ask), deletes the local
   and remote branches whose PR merged (keeping and listing any it cannot confirm), re-arms your
   PRs whose auto-merge GitHub never fired (see Troubleshooting), then branches from a
   freshly fetched `main`. Never push to `main` directly -- branch protection rejects it for
   everyone, administrators included.
2. **Open the PR.** `python3 ${CLAUDE_SKILL_DIR}/scripts/open_pr.py` pushes the branch and runs
   `gh pr create --fill`.
3. **Review the PR.** Run `/code-review <pr>` in this session. Apply the findings worth
   applying on the PR's branch, in the checkout step 1 made -- a commit made in any other
   checkout is not in the PR -- and push
   any fixes **as new commits -- the branch is already pushed and under
   review, so never amend, rebase, or force-push it; the squash-merge in step 4 collapses every
   commit into one on `main`, so branch commit count does not matter.** Dismiss the rest with a
   one-line reason. Review once -- do not loop on further advisory findings; record any
   leftover suggestion as a follow-up issue.
4. **Merge and return to `main`.** Once the commit is final,
   `python3 ${CLAUDE_SKILL_DIR}/scripts/finish_branch.py <pr>` arms a squash auto-merge and,
   in the main checkout, returns to `main`; from a worktree, leave it with `ExitWorktree`.
   Squash collapses the branch's commits into a single commit on `main`, so the branch itself
   may carry several commits (initial work plus review fixes). Arming auto-merge is what
   authorizes the merge, so do it only after addressing the review -- never before. GitHub then merges the moment
   `verify` is green; you do not watch the run, and the next `start_branch` deletes the branch
   and its worktree once the PR has merged. When the PR needs you, the script stops and says
   why (see Troubleshooting).

Pause for explicit approval before pushing risky or ambiguous changes. Commit-message
conventions live in the repo's `CLAUDE.md`.

## Where things stand

An issue stays open until its PR merges: GitHub closes a `Resolves #N` issue only when the commit
reaches the default branch. So `gh issue ls` lists the open work, and `gh pr ls` is empty unless
a PR has not merged yet -- its CI is still running, it is stuck, or another session is still
working on it. `gh pr checks <pr>` and `gh pr view <pr>` say which; Troubleshooting covers the
stuck cases.

## Troubleshooting

- **PR will not merge -- "no checks reported."** A push can land without firing CI, so no
  `verify` run attaches and auto-merge cannot arm. Close and reopen the PR to re-fire CI.
- **An open PR does not merge.** Auto-merge stays armed through each fix below, so pushing it
  is enough:
  - *Conflict with `main`:* another PR changed the same lines. Merge `main` into the branch,
    resolve, and push a new commit (never rebase or force-push). `finish_branch.py` exits 3 on
    a conflict it sees.
  - *A required check failed:* push a fix as a new commit, or re-run the check if it was flaky.
  - *Auto-merge not armed:* re-run `finish_branch.py` (step 4), which arms it.
  - *Armed, CLEAN, and green, yet open:* GitHub sometimes never fires an armed merge. The next
    `start_branch.py` re-arms such a PR once it has sat ready for a few minutes; to nudge it
    sooner, run `gh pr merge <pr> --disable-auto`, then re-run `finish_branch.py` (step 4).
  - *Behind `main`:* the repo requires branches to be up to date (see Background). Run
    `gh pr update-branch <pr>` (it merges `main` in, never rebases), and turn that requirement off.
- **A merged PR's branch is back on the remote.** A push made after GitHub merged the PR
  recreates the branch, with no PR behind it. An armed PR needs a push only to fix a conflict or
  a failed check -- a conflicting PR cannot merge in the meantime -- so do not push it otherwise.
  The next `start_branch.py` deletes such a branch if it holds nothing new, and otherwise keeps
  and lists it: open a PR for what it holds.
