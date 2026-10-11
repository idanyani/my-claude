#!/usr/bin/env python3
"""Finish a resolved issue: confirm GitHub will merge its PR without a person, then return to `main`.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr> [--worktree]

Run it right after arming auto-merge. It checks only what GitHub knows within seconds -- the PR
merged, or auto-merge is armed and the PR has no conflict with `main` -- polling briefly while
GitHub settles, and never waits for CI. Whatever surfaces later (a failed check, a conflict with a
PR merged after this one, CI that never starts) leaves the PR open, where `gh pr ls` lists it (see
references/git-workflow.md). The next start_branch.py deletes the merged branch.

In place, it checks out an up-to-date `main`; with `--worktree`, it leaves the sibling worktree for
the next start_branch.py to remove.

Exit 0: the PR merged, or will merge once its checks pass; the message says which, or that GitHub
    was still checking it for conflicts.
Exit 1: the PR closed without merging, or a git/gh call failed.
Exit 3: the PR needs a person -- it conflicts with main, or auto-merge is not armed; the message
    names which. Fix that and re-run.
"""

import sys
import time

from lib.gh import run_gh, run_git
from lib.merge import SETTLING, arm_verdict, parse_args

POLL_INTERVAL_SECONDS = 5
POLL_LIMIT = 6
EXIT_NEEDS_ATTENTION = 3


def pr_verdict(pr: str) -> str:
    view = run_gh(["pr", "view", pr, "--json", "state,mergeable,autoMergeRequest"])
    return arm_verdict(view["state"], view["mergeable"], view["autoMergeRequest"] is not None)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    verdict = pr_verdict(args.pr)
    for _ in range(POLL_LIMIT - 1):
        if verdict not in SETTLING:
            break
        time.sleep(POLL_INTERVAL_SECONDS)
        verdict = pr_verdict(args.pr)

    if verdict == "closed":
        print(f"PR #{args.pr} is CLOSED without merging.", file=sys.stderr)
        return 1
    if verdict == "conflict":
        print(
            f"PR #{args.pr} conflicts with main -- merge main into the branch, resolve, push a new "
            "commit, and re-run.",
            file=sys.stderr,
        )
        return EXIT_NEEDS_ATTENTION
    if verdict == "unarmed":
        print(
            f"PR #{args.pr} has no auto-merge armed, so nothing will merge it -- run "
            "`gh pr merge --auto --squash --delete-branch` and re-run.",
            file=sys.stderr,
        )
        return EXIT_NEEDS_ATTENTION

    if not args.worktree:
        run_git(["checkout", "main"])
        run_git(["pull", "--ff-only"])
    if verdict == "merged":
        print(f"PR #{args.pr} merged.")
    elif verdict == "armed":
        print(
            f"PR #{args.pr} will merge once its required checks pass; `gh pr ls` lists it until then."
        )
    else:
        print(
            f"GitHub was still checking PR #{args.pr} for conflicts; `gh pr ls` lists it until it "
            "merges."
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
