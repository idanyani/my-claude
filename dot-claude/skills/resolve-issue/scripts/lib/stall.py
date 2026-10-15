"""Re-arm the user's own PRs whose armed squash auto-merge GitHub never fired.

GitHub sometimes leaves an armed PR open after its checks pass, with the PR reading CLEAN; turning
auto-merge off and on again makes GitHub merge it (idanyani/my-claude#93). Re-arming goes through
the same `arm_auto_merge` call finish_branch.py makes, so on a PR gh reads as ready it merges at
once. Only PRs armed as a squash -- the method that call re-arms with -- are touched, so a method
picked by hand is never overridden.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from lib.gh import arm_auto_merge, run_gh, run_gh_text

# GitHub merges an armed PR within seconds of its last check passing; both observed stalls
# lasted more than 7 minutes.
STALL_AFTER_SECONDS = 300
REARMED = "re-armed"
MERGED = "merged"
PR_FIELDS = "number,state,mergeStateStatus,autoMergeRequest,statusCheckRollup"
# A commit status (StatusContext) in these states has not finished.
UNFINISHED_STATUS_STATES = ("PENDING", "EXPECTED")


def _finished_at(check: dict[str, Any]) -> datetime | None:
    """When a `statusCheckRollup` entry finished, or None while it runs.

    A check run records its completion; a commit status records only when it was set.
    """
    if check["__typename"] == "CheckRun":
        if check["status"] != "COMPLETED":
            return None
        return datetime.fromisoformat(check["completedAt"])
    if check["state"] in UNFINISHED_STATUS_STATES:
        return None
    return datetime.fromisoformat(check["startedAt"])


def green_since(pr: dict[str, Any]) -> datetime | None:
    """Since when an armed PR has had nothing left to wait for, or None while a check runs."""
    moments = [datetime.fromisoformat(pr["autoMergeRequest"]["enabledAt"])]
    for check in pr["statusCheckRollup"]:
        finished = _finished_at(check)
        if finished is None:
            return None
        moments.append(finished)
    return max(moments)


def stalled_prs(prs: list[dict[str, Any]], now: datetime) -> list[str]:
    """The numbers of the open, armed, CLEAN PRs that have been green for the stall threshold."""
    stalled = []
    for pr in prs:
        if pr["state"] != "OPEN" or pr["autoMergeRequest"] is None:
            continue
        if pr["autoMergeRequest"]["mergeMethod"] != "SQUASH":
            continue
        if pr["mergeStateStatus"] != "CLEAN":
            continue
        since = green_since(pr)
        if since is not None and now - since >= timedelta(seconds=STALL_AFTER_SECONDS):
            stalled.append(str(pr["number"]))
    return stalled


def rearm_stalled_prs() -> dict[str, str]:
    """Turn auto-merge off and on for each of the user's stalled PRs.

    Returns each stalled PR mapped to `REARMED`, `MERGED`, or what went wrong.
    """
    prs = run_gh(["pr", "list", "--author", "@me", "--state", "open", "--json", PR_FIELDS])
    return {pr: _rearm(pr) for pr in stalled_prs(prs, datetime.now(UTC))}


def _rearm(pr: str) -> str:
    """Turn one PR's auto-merge off and on; return `REARMED`, `MERGED`, or what went wrong.

    A failed step is no proof the PR is still open: GitHub may have merged it since the listing,
    and gh merges a ready PR at once and can then fail deleting a branch a worktree holds.
    """
    try:
        run_gh_text(["pr", "merge", pr, "--disable-auto"])
    except RuntimeError as error:
        return MERGED if _merged(pr) else str(error)
    try:
        arm_auto_merge(pr)
    except RuntimeError as error:
        if _merged(pr):
            return MERGED
        return (
            f"auto-merge is now unarmed -- re-arming failed: {error} -- run finish_branch.py {pr}"
        )
    return REARMED


def _merged(pr: str) -> bool:
    return run_gh(["pr", "view", pr, "--json", "state"])["state"] == "MERGED"
