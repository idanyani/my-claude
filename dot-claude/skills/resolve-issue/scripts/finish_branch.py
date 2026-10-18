#!/usr/bin/env python3
"""Finish a resolved issue: arm its PR's auto-merge, confirm GitHub will merge it, return to `main`.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr>

Unless the PR already merged or closed, it first refuses while a local branch or worktree HEAD of
this repo holds commits that build on the PR but are not in it (lib/unpushed.py), so a merge cannot
leave them behind. Then it arms auto-merge (squash, deleting the remote branch), retrying while GitHub refuses, and checks
only what GitHub knows within seconds -- the PR merged, or auto-merge is armed and the PR has no
conflict with `main` -- polling briefly while GitHub settles. It never waits for CI. Whatever
surfaces later (a failed check, a conflict with a PR merged after this one, CI that never starts)
leaves the PR open, where `gh pr ls` lists it (see references/git-workflow.md). The next
start_branch.py deletes the merged branch, and re-arms the PR if GitHub never fired its merge.

In the main checkout, it checks out an up-to-date `main`. In a linked worktree it leaves the
checkout alone; the next start_branch.py's sweep removes the worktree once the PR has merged.

Exit 0: the PR merged, or will merge once its checks pass; the message says which, or that GitHub
    was still checking it for conflicts.
Exit 1: the PR closed without merging, or a git/gh call failed.
Exit 3: the PR needs a person -- local commits build on it without being in it, it conflicts with
    main, or GitHub kept refusing to arm auto-merge; the message names which. Fix that and re-run.
"""

import sys
import time

from lib.gh import arm_auto_merge, in_linked_worktree, run_gh, run_git
from lib.merge import SETTLING, arm_verdict, parse_args
from lib.unpushed import commits_missing_from_pr

POLL_INTERVAL_SECONDS = 5
POLL_LIMIT = 6
EXIT_NEEDS_ATTENTION = 3


def pr_verdict(pr: str) -> str:
    view = run_gh(["pr", "view", pr, "--json", "state,mergeable,autoMergeRequest"])
    return arm_verdict(view["state"], view["mergeable"], view["autoMergeRequest"] is not None)


def report_missing_commits(pr: str, missing: dict[str, list[str]]) -> None:
    print(f"Local commits build on PR #{pr} but are not in it:", file=sys.stderr)
    for tip, commits in missing.items():
        print(f"  {tip}:", file=sys.stderr)
        for line in commits:
            print(f"    {line}", file=sys.stderr)
    print(
        "Push the ones the PR needs to its branch as new commits (cherry-pick them onto it if they "
        "were made elsewhere), delete the rest, and re-run.",
        file=sys.stderr,
    )


def main(argv: list[str]) -> int:
    pr = parse_args(argv)
    verdict = pr_verdict(pr)
    # Arming authorizes the merge, so first make sure no local work on the PR is left behind
    # (idanyani/my-claude#95); a merged or closed PR has nothing left to authorize.
    if verdict not in ("merged", "closed"):
        missing = commits_missing_from_pr(pr)
        if missing:
            report_missing_commits(pr, missing)
            return EXIT_NEEDS_ATTENTION
    # What the last arm attempt reported, success or refusal, for an exit-3 message.
    arm_outcome = "not attempted"
    for _ in range(POLL_LIMIT - 1):
        if verdict not in SETTLING:
            break
        if verdict == "unarmed":
            # gh picks "merge now" over "enable auto-merge" from a status that, right after a push,
            # can still describe the previous head, and GitHub then refuses; a refused attempt
            # changes nothing, so the next poll retries it (idanyani/my-claude#71).
            try:
                arm_outcome = arm_auto_merge(pr) or "gh reported nothing"
            except RuntimeError as error:
                arm_outcome = str(error)
        time.sleep(POLL_INTERVAL_SECONDS)
        verdict = pr_verdict(pr)

    if verdict == "closed":
        print(f"PR #{pr} is CLOSED without merging.", file=sys.stderr)
        return 1
    if verdict == "conflict":
        print(
            f"PR #{pr} conflicts with main -- merge main into the branch, resolve, push a new "
            "commit, and re-run.",
            file=sys.stderr,
        )
        return EXIT_NEEDS_ATTENTION
    if verdict == "unarmed":
        print(
            f"PR #{pr} is still not armed for auto-merge; the last attempt reported: "
            f"{arm_outcome} -- if no check has run, see Troubleshooting in "
            "references/git-workflow.md; then re-run.",
            file=sys.stderr,
        )
        return EXIT_NEEDS_ATTENTION

    # Report the verdict before touching the checkout, so a failed pull cannot hide it.
    if verdict == "merged":
        print(f"PR #{pr} merged.")
    elif verdict == "armed":
        print(
            f"PR #{pr} has auto-merge armed and no conflict with main; it merges once its "
            f"required checks pass (`gh pr checks {pr}`)."
        )
    else:
        print(
            f"PR #{pr} has auto-merge armed; GitHub was still checking it for conflicts. "
            "`gh pr ls` lists it until it merges."
        )
    # A linked worktree cannot check out `main` while the main checkout holds it.
    if not in_linked_worktree():
        run_git(["checkout", "main"])
        run_git(["pull", "--ff-only"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
