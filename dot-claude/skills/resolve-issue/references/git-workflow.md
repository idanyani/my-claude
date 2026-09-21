# Git Workflow

Every change reaches `main` the same way: a short-lived branch, a pull request, and a
squash-merge once CI passes. This is the canonical workflow doc; each consuming repo's
`docs/git-workflow.md` stub links here instead of repeating it, and holds only the
repo-specifics (what `verify` runs, where its CI workflow lives).

The helper scripts live in this skill's `scripts/` directory and are invoked as plain files:
`python3 <skill-dir>/scripts/<name>.py`. They are stdlib-only and need just `python3`, `git`,
and `gh` on PATH; they run against the current working directory's repo.

## Background

- **Pull request (PR):** a request to merge a branch into `main`. GitHub runs CI on it and
  shows reviews before it merges.
- **`verify`:** the project's CI check -- what it runs is repo-specific and named in the
  repo's `docs/git-workflow.md` stub or `CLAUDE.md`. It is the one *required* check: branch
  protection refuses to merge until it passes.
- **Auto-merge:** GitHub merges the PR by itself once `verify` passes, so you do not watch
  the run.
- **Copilot review:** an automated review GitHub posts on a new PR. It is *advisory* -- it
  never gates the merge; you read it and decide, and `verify` is the only gate. If Copilot
  code review is not enabled on the org, the helper scripts below simply time out or no-op;
  nothing breaks. When Copilot is over quota or otherwise unavailable, or its review never
  posts, fall back to an in-session `/code-review <pr>` so the PR still gets reviewed.

## Steps

1. **Branch from `main`.** `python3 <skill-dir>/scripts/start_branch.py <number>
   <kebab-summary>` (add `--worktree` for a sibling worktree; the script prints the
   dependency-install command the fresh worktree needs). It refuses a dirty tree (it never
   stashes silently -- surface that and ask), prunes `[gone]` branches, then branches from a
   freshly pulled `main`. Never push to `main` directly -- branch protection rejects it for
   everyone, administrators included.
2. **Open the PR.** `git push -u origin <branch>`, then `gh pr create --fill`.
3. **Address Copilot's review.** Copilot posts an advisory review under the `[bot]`-suffixed
   login `copilot-pull-request-reviewer[bot]` -- usually a minute or two after the push,
   occasionally several. `python3 <skill-dir>/scripts/wait_for_copilot_review.py <pr>` reads
   that review over the REST API and blocks on the review stream alone (not CI, which is an
   independent event stream auto-merge already handles) for up to five minutes, then returns
   so you move on. It exits **0** when a genuine review posts -- printing the overview body
   and every inline finding as a `path:line` anchor, so you can act on them directly --
   **2** when the wait expires with no review, and **3** when Copilot posts an "unable to
   review" notice (e.g. over quota). On **2 or 3**, no Copilot review exists to address: run
   an in-session `/code-review <pr>` and address its findings before arming auto-merge in step 4,
   so the PR never merges unreviewed. On **0**, apply the comments worth applying and push any
   fixes **as new commits -- the branch is already pushed and under review, so never amend,
   rebase, or force-push it; the squash-merge in step 4 collapses every commit into one on
   `main`, so branch commit count does not matter.** Dismiss the rest with a one-line reason.
   Copilot does not re-review later
   pushes on its own, so if you pushed substantive changes, request one more on your final
   commit with `python3 <skill-dir>/scripts/request_copilot_review.py <pr>` (it wraps the
   REST endpoint to sidestep the `projectCards` GraphQL deprecation noted below). Address
   the review once -- do not loop on further advisory comments; record any leftover
   suggestion as a follow-up issue.
4. **Merge.** Once the commit is final, `gh pr merge --auto --squash --delete-branch`.
   Squash is what collapses the branch's commits into a single commit on `main` -- that is the
   guarantee, so the branch itself may carry several commits (initial work plus review fixes).
   Arming auto-merge is what authorizes the
   merge, so do it only after addressing the review -- never before. GitHub then merges the
   moment `verify` is green (immediately, if it already is) and notifies you; you do not
   watch the run yourself.
5. **Return to `main` and clean up.** `python3 <skill-dir>/scripts/finish_branch.py <pr>`
   waits for the merge, then syncs `main` and deletes the local branch (with `--worktree`,
   it first removes the sibling worktree). To skip the wait, just `git checkout main` and
   let the merge land asynchronously -- the next `start_branch` deletes the `[gone]` branch.

Pause for explicit approval before pushing risky or ambiguous changes. Commit-message
conventions live in the repo's `CLAUDE.md`.

## Troubleshooting

- **PR will not merge -- "no checks reported."** A push can land without firing CI, so no
  `verify` run attaches and auto-merge cannot arm. Close and reopen the PR to re-fire CI.
- **`gh pr edit --add-reviewer` errors with a `projectCards` GraphQL deprecation.** Request
  Copilot through `python3 <skill-dir>/scripts/request_copilot_review.py <pr>` (it uses the
  REST endpoint) instead.
