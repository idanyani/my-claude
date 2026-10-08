#!/usr/bin/env python3
"""Finish a resolved issue: wait for its PR to merge, then clean up the local branch.

Usage: python3 <skill-dir>/scripts/finish_branch.py <pr> [--worktree] [--timeout-seconds N]

Launch it with the Bash tool's `run_in_background`: the default wait outlasts the tool's
foreground timeout, which would kill it mid-wait and skip the cleanup.

Waits on the PR's merge state, bounded by `--timeout-seconds` without progress: bringing a
`BEHIND` PR up to date restarts the clock, so a PR waiting its turn behind other merges is not cut
off. On a repo whose branch protection requires branches to be up to date, another PR's merge
leaves this one `BEHIND`, and auto-merge never updates it; the wait then runs `gh pr
update-branch` (a merge, never a rebase, so the pushed history stays intact) and lets CI and
auto-merge take it from there. A PR that cannot merge until a person acts ends the wait at once
instead of using up the window. The remote branch is already deleted by `--delete-branch`
on auto-merge (see references/git-workflow.md), so cleanup is the local side: sync `main` and
delete the local branch -- or remove the sibling worktree first with `--worktree`. A squash merge
leaves the branch "not fully merged" to git, so deletion is a forced `-D` only after GitHub
confirms the merge, never a plain `-d` on an unmerged branch.

Exit 0: merged and cleaned up.
Exit 1: the PR closed without merging, or a git/gh call failed.
Exit 2: the bounded wait expired with the PR still open and nothing failed -- the caller
    proceeds; the next start-branch / clean-gone removes the branch once it goes [gone].
Exit 3: the PR needs a person -- it conflicts with main, a required check failed, or auto-merge
    is not armed; the message names which. Fix that and re-run.
"""

import os
import subprocess
import sys
import time
from typing import Any

from lib.gh import run_gh, run_gh_text, run_git
from lib.merge import (
    PrStatus,
    branch_deletion_plan,
    failed_required_checks,
    merge_decision,
    parse_args,
    parse_main_worktree,
    parse_required_checks,
    parse_worktree_for_branch,
)

POLL_INTERVAL_SECONDS = 20
EXIT_NEEDS_ATTENTION = 3


def pr_view(pr: str) -> dict[str, Any]:
    return run_gh(
        [
            "pr",
            "view",
            pr,
            "--json",
            "state,mergeStateStatus,headRefName,headRefOid,autoMergeRequest",
        ]
    )


def required_checks(pr: str) -> list[dict[str, str]]:
    # Not run_gh: `gh pr checks` exits nonzero for a head with no checks yet.
    result = subprocess.run(
        ["gh", "pr", "checks", pr, "--required", "--json", "name,bucket"],
        capture_output=True,
        text=True,
    )
    return parse_required_checks(result.returncode, result.stdout, result.stderr)


def pr_status(pr: str, view: dict[str, Any]) -> PrStatus:
    open_ = view["state"] == "OPEN"
    return PrStatus(
        state=view["state"],
        merge_state_status=view["mergeStateStatus"],
        head_oid=view["headRefOid"],
        auto_merge_armed=view["autoMergeRequest"] is not None,
        # A merged or closed PR needs no check verdict, so skip the extra call.
        failed_checks=failed_required_checks(required_checks(pr)) if open_ else (),
    )


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


def is_ancestor(pr: str, local_oid: str, pr_head_oid: str) -> bool:
    """Whether the local tip is contained in the merged PR head.

    A head GitHub advanced with an update-branch merge commit exists only on the remote, so fetch
    it from the PR ref, which outlives the deleted branch.
    """
    if local_oid == pr_head_oid:
        return True
    run_git(["fetch", "origin", f"pull/{pr}/head"])
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", local_oid, pr_head_oid],
        capture_output=True,
        text=True,
    )
    # Exit 1 is a definite "no"; any other nonzero status is a real failure that must surface
    # rather than masquerade as a diverged branch.
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise RuntimeError(
        f"git merge-base --is-ancestor exited {result.returncode}: {result.stderr.strip()}"
    )


def sync_main() -> None:
    run_git(["checkout", "main"])
    run_git(["pull", "--ff-only"])
    run_git(["fetch", "--prune"])


def clean_up(pr: str, branch: str, head_ref_oid: str, worktree: bool) -> None:
    porcelain = run_git(["worktree", "list", "--porcelain"])
    # Operate from the main checkout: in worktree mode this is typically invoked from inside the
    # worktree being removed, where `git checkout main` would fail (main is checked out here) and a
    # post-removal cwd would point at a deleted directory. chdir away first so neither bites.
    os.chdir(parse_main_worktree(porcelain))

    # Decide before touching anything: an absent branch is already cleaned up (a no-op, not an
    # error); a present branch is deletable only once its tip is confirmed to be what GitHub merged.
    local_oid = local_branch_oid(branch)
    plan = branch_deletion_plan(
        local_oid,
        branch,
        head_ref_oid,
        local_is_ancestor=local_oid is not None and is_ancestor(pr, local_oid, head_ref_oid),
    )

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
    idle_start = time.monotonic()
    updated_from_oid: str | None = None
    unarmed_seen = False

    while True:
        view = pr_view(args.pr)
        pr = pr_status(args.pr, view)
        idle_ms = (time.monotonic() - idle_start) * 1000
        outcome = merge_decision(pr, updated_from_oid, idle_ms, args.timeout_ms)

        if outcome == "merged":
            clean_up(args.pr, view["headRefName"], pr.head_oid, args.worktree)
            return 0
        if outcome == "closed":
            print(
                f"PR #{args.pr} is CLOSED without merging -- leaving the branch in place.",
                file=sys.stderr,
            )
            return 1
        if outcome == "conflict":
            print(
                f"PR #{args.pr} conflicts with main -- resolve it by hand and re-run.",
                file=sys.stderr,
            )
            return EXIT_NEEDS_ATTENTION
        # Confirm "unarmed" on a second poll before giving up: GitHub clears the auto-merge request
        # as it merges, so one poll can land between that and the MERGED state.
        if outcome == "unarmed" and not unarmed_seen:
            unarmed_seen = True
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        unarmed_seen = False
        if outcome == "unarmed":
            print(
                f"PR #{args.pr} has no auto-merge armed, so nothing will merge it -- run "
                "`gh pr merge --auto --squash --delete-branch` (or merge by hand) and re-run.",
                file=sys.stderr,
            )
            return EXIT_NEEDS_ATTENTION
        if outcome == "check_failed":
            print(
                f"PR #{args.pr} failed required check(s) {', '.join(pr.failed_checks)} -- fix or "
                "re-run them, then re-run; auto-merge stays armed.",
                file=sys.stderr,
            )
            return EXIT_NEEDS_ATTENTION
        if outcome == "update":
            try:
                run_gh_text(["pr", "update-branch", args.pr])
                print(f"PR #{args.pr} was behind main -- updated it; CI reruns.")
                idle_start = time.monotonic()
                updated_from_oid = pr.head_oid
            except RuntimeError as error:
                # Non-fatal: auto-merge stays armed, and a stale BEHIND status or another actor's
                # update can make the call fail on a branch that no longer needs it. The next poll
                # retries a PR still BEHIND; the idle clock, left running, bounds repeated failures.
                print(f"PR #{args.pr} update failed; still waiting: {error}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if outcome == "timeout":
            print(
                f"PR #{args.pr} not merged after {args.timeout_ms / 1000:g}s without progress "
                f"(still OPEN, merge state {pr.merge_state_status}, no required check failed) -- "
                "proceeding; the next start-branch / clean-gone removes the branch once it goes "
                "[gone].",
                file=sys.stderr,
            )
            return 2
        # Cap the sleep to the time left so a full interval cannot overshoot --timeout-seconds.
        time.sleep(min(POLL_INTERVAL_SECONDS, (args.timeout_ms - idle_ms) / 1000))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
