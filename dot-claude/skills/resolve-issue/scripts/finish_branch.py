#!/usr/bin/env python3
"""Finish a resolved issue: arm its PR's auto-merge, confirm GitHub will merge it, return to `main`.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr>

Unless the PR already merged or closed, it first refuses while a local branch or worktree HEAD of
this repo holds commits that build on the PR but are not in it (lib/unpushed.py), so a merge cannot
leave them behind. Then it arms auto-merge (squash, deleting the remote branch, pinned to the head
that check measured), retrying while GitHub refuses, and checks only what GitHub knows within
seconds -- the PR merged, or auto-merge is armed and the PR has no conflict with `main` -- polling
briefly while GitHub settles, and until GitHub's view names that head. It never waits for CI.
Whatever surfaces later (a failed check, a conflict with a PR merged after this one, CI that never starts)
leaves the PR open, where `gh pr ls` lists it (see references/git-workflow.md). The next
start_branch.py deletes the merged branch, re-arms the PR if GitHub never fired its merge, and
reopens it if its CI never started.

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


def view_pr(pr: str) -> dict:
    return run_gh(["pr", "view", pr, "--json", "state,mergeable,autoMergeRequest,headRefOid"])


def verdict_of(view: dict, checked_head: str) -> str:
    """`arm_verdict` of a `view_pr` result, as of `checked_head`.

    A moment after a push GitHub's view still names the previous head, whose mergeability says
    nothing about the head checked, so it counts as not yet known.
    """
    current = view["headRefOid"] == checked_head
    mergeable = view["mergeable"] if current else "UNKNOWN"
    return arm_verdict(view["state"], mergeable, view["autoMergeRequest"] is not None)


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
    view = view_pr(pr)
    checked_head = view["headRefOid"]
    # Arming authorizes the merge, so first make sure no local work on the PR is left behind, and
    # pin the merge, and every verdict after it, to the head that check measured; a merged or
    # closed PR has nothing left to authorize.
    if view["state"] not in ("MERGED", "CLOSED"):
        checked_head, missing = commits_missing_from_pr(pr)
        if missing:
            report_missing_commits(pr, missing)
            return EXIT_NEEDS_ATTENTION
    verdict = verdict_of(view, checked_head)
    # What the last arm attempt reported, success or refusal, for an exit-3 message.
    arm_outcome = "not attempted"
    for _ in range(POLL_LIMIT - 1):
        if verdict not in SETTLING:
            break
        if verdict == "unarmed":
            # Right after a push GitHub's PR can still describe the previous head: gh may then
            # pick "merge now" over "enable auto-merge", and the head pin fails. GitHub refuses
            # either way, a refused attempt changes nothing, and the next poll retries it.
            try:
                arm_outcome = arm_auto_merge(pr, checked_head) or "gh reported nothing"
            except RuntimeError as error:
                arm_outcome = str(error)
        time.sleep(POLL_INTERVAL_SECONDS)
        verdict = verdict_of(view_pr(pr), checked_head)

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
