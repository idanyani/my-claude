#!/usr/bin/env python3
"""Finish a resolved issue: arm its PR's auto-merge, confirm GitHub will merge it, return to `main`.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr> [--worktree]

It arms auto-merge (squash, deleting the remote branch), retrying while GitHub refuses, and checks
only what GitHub knows within seconds -- the PR merged, or auto-merge is armed and the PR has no
conflict with `main` -- polling briefly while GitHub settles. It never waits for CI. Whatever
surfaces later (a failed check, a conflict with a PR merged after this one, CI that never starts)
leaves the PR open, where `gh pr ls` lists it (see references/git-workflow.md). The next
start_branch.py deletes the merged branch.

In place, it checks out an up-to-date `main`. With `--worktree`, it names the main checkout to `cd`
to, so the next start_branch.py runs from there and its sweep can remove the sibling worktree.

Exit 0: the PR merged, or will merge once its checks pass; the message says which, or that GitHub
    was still checking it for conflicts.
Exit 1: the PR closed without merging, or a git/gh call failed.
Exit 3: the PR needs a person -- it conflicts with main, or GitHub kept refusing to arm
    auto-merge; the message names which. Fix that and re-run.
"""

import sys
import time

from lib.gh import run_gh, run_gh_text, run_git
from lib.merge import SETTLING, arm_verdict, parse_args
from lib.sweep import parse_main_worktree

POLL_INTERVAL_SECONDS = 5
POLL_LIMIT = 6
EXIT_NEEDS_ATTENTION = 3


def pr_verdict(pr: str) -> str:
    view = run_gh(["pr", "view", pr, "--json", "state,mergeable,autoMergeRequest"])
    return arm_verdict(view["state"], view["mergeable"], view["autoMergeRequest"] is not None)


def arm_auto_merge(pr: str) -> str:
    """Arm auto-merge, or merge at once if gh reads the PR as ready; returns what gh reported."""
    return run_gh_text(["pr", "merge", pr, "--auto", "--squash", "--delete-branch"]).strip()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    # What the last arm attempt reported, success or refusal, for an exit-3 message.
    arm_outcome = "not attempted"
    verdict = pr_verdict(args.pr)
    for _ in range(POLL_LIMIT - 1):
        if verdict not in SETTLING:
            break
        if verdict == "unarmed":
            # gh picks "merge now" over "enable auto-merge" from a status that, right after a push,
            # can still describe the previous head, and GitHub then refuses; a refused attempt
            # changes nothing, so the next poll retries it (idanyani/my-claude#71).
            try:
                arm_outcome = arm_auto_merge(args.pr) or "gh reported nothing"
            except RuntimeError as error:
                arm_outcome = str(error)
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
            f"PR #{args.pr} is still not armed for auto-merge; the last attempt reported: "
            f"{arm_outcome} -- if no check has run, see Troubleshooting in "
            "references/git-workflow.md; then re-run.",
            file=sys.stderr,
        )
        return EXIT_NEEDS_ATTENTION

    # Report the verdict before touching the checkout, so a failed pull cannot hide it.
    if verdict == "merged":
        print(f"PR #{args.pr} merged.")
    elif verdict == "armed":
        print(
            f"PR #{args.pr} has auto-merge armed and no conflict with main; it merges once its "
            f"required checks pass (`gh pr checks {args.pr}`)."
        )
    else:
        print(
            f"PR #{args.pr} has auto-merge armed; GitHub was still checking it for conflicts. "
            "`gh pr ls` lists it until it merges."
        )
    if args.worktree:
        main_checkout = parse_main_worktree(run_git(["worktree", "list", "--porcelain"]))
        # Leaving the worktree lets the next start_branch.py's sweep remove it.
        print(f"Left the worktree in place -- `cd {main_checkout}` to leave it.")
    else:
        run_git(["checkout", "main"])
        run_git(["pull", "--ff-only"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
