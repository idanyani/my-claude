#!/usr/bin/env python3
"""Finish a resolved issue: wait for its PR to merge, then clean up the local branch.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr> [--worktree] [--timeout-seconds N]

Bounded-waits on the PR's merge state. The remote branch is already deleted by `--delete-branch`
on auto-merge (see references/git-workflow.md), so cleanup is the local side: sync `main` and
delete the local branch -- or remove the sibling worktree first with `--worktree`. A squash merge
leaves the branch "not fully merged" to git, so deletion is a forced `-D` only after GitHub
confirms the merge, never a plain `-d` on an unmerged branch.

Exit 0: merged and cleaned up.
Exit 2: the bounded wait expired (merge still pending) -- the caller proceeds; the next
    start-branch / clean-gone removes the branch once it goes [gone].
Exit 1: the PR closed without merging, or a git/gh call failed.
"""

import os
import subprocess
import sys
import time
from typing import Any

from lib.gh import run_gh, run_git
from lib.merge import (
    branch_deletion_plan,
    merge_decision,
    parse_args,
    parse_main_worktree,
    parse_worktree_for_branch,
)

POLL_INTERVAL_SECONDS = 20


def pr_state(pr: str) -> dict[str, Any]:
    return run_gh(["pr", "view", pr, "--json", "state,headRefName,headRefOid"])


def local_branch_oid(branch: str) -> str | None:
    """The local branch's tip OID, or None when the branch does not exist."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # `--quiet` exits 1 for a genuinely missing ref; any other status is a real failure (bad
    # refname, not a repo) that must surface rather than masquerade as "already removed".
    if result.returncode == 1:
        return None
    raise RuntimeError(
        f"git rev-parse refs/heads/{branch} exited {result.returncode}: {result.stderr.strip()}"
    )


def sync_main() -> None:
    run_git(["checkout", "main"])
    run_git(["pull", "--ff-only"])
    run_git(["fetch", "--prune"])


def clean_up(branch: str, head_ref_oid: str, worktree: bool) -> None:
    porcelain = run_git(["worktree", "list", "--porcelain"])
    # Operate from the main checkout: in worktree mode this is typically invoked from inside the
    # worktree being removed, where `git checkout main` would fail (main is checked out here) and a
    # post-removal cwd would point at a deleted directory. chdir away first so neither bites.
    os.chdir(parse_main_worktree(porcelain))

    # Decide before touching anything: an absent branch is already cleaned up (a no-op, not an
    # error); a present branch is deletable only once its tip is confirmed to be what GitHub merged.
    plan = branch_deletion_plan(local_branch_oid(branch), branch, head_ref_oid)

    # Remove the sibling worktree whether or not the branch ref still exists, so `--worktree` never
    # leaves the directory behind. Remove it before deleting the branch -- git refuses to delete a
    # branch checked out in a worktree.
    removed_worktree = False
    if worktree:
        path = parse_worktree_for_branch(porcelain, branch)
        if path:
            run_git(["worktree", "remove", path])
            removed_worktree = True
    sync_main()
    if plan == "delete":
        # Forced: a squash merge leaves the branch not-fully-merged to git.
        run_git(["branch", "-D", branch])
    if plan == "absent":
        message = f"Branch {branch} was already removed; synced main."
    elif removed_worktree:
        message = f"Removed worktree, synced main, deleted merged branch {branch}."
    else:
        message = f"Synced main and deleted merged branch {branch}."
    print(message)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    start = time.monotonic()

    while True:
        state = pr_state(args.pr)
        elapsed_ms = (time.monotonic() - start) * 1000
        outcome = merge_decision(state["state"], elapsed_ms, args.timeout_ms)

        if outcome == "merged":
            clean_up(state["headRefName"], state["headRefOid"], args.worktree)
            return 0
        if outcome == "closed":
            print(
                f"PR #{args.pr} is CLOSED without merging -- leaving the branch in place.",
                file=sys.stderr,
            )
            return 1
        if outcome == "timeout":
            print(
                f"PR #{args.pr} not merged after {args.timeout_ms / 1000:g}s -- proceeding; "
                "the next start-branch / clean-gone removes the branch once it goes [gone].",
                file=sys.stderr,
            )
            return 2
        # Cap the sleep to the time left so a full interval cannot overshoot --timeout-seconds.
        time.sleep(min(POLL_INTERVAL_SECONDS, (args.timeout_ms - elapsed_ms) / 1000))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
