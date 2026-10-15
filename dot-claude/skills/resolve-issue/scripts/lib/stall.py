"""Re-arm the session's own PRs whose armed auto-merge GitHub never fired.

GitHub sometimes leaves an armed PR open after its checks pass, with the PR reading CLEAN; turning
auto-merge off and on again makes GitHub merge it (idanyani/my-claude#93). Re-arming rather than
merging directly keeps the merge gated on CI. Only the user's own PRs are touched.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from lib.gh import arm_auto_merge, run_gh, run_gh_text

# GitHub merges an armed PR within seconds of its last check passing; both observed stalls
# lasted more than 7 minutes.
STALL_AFTER_SECONDS = 300
REARMED = "re-armed"
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
        if pr["mergeStateStatus"] != "CLEAN":
            continue
        since = green_since(pr)
        if since is not None and now - since >= timedelta(seconds=STALL_AFTER_SECONDS):
            stalled.append(str(pr["number"]))
    return stalled


def rearm_stalled_prs() -> dict[str, str]:
    """Turn auto-merge off and on for each of the user's stalled PRs.

    Returns each stalled PR mapped to `REARMED` or to what went wrong.
    """
    prs = run_gh(["pr", "list", "--author", "@me", "--state", "open", "--json", PR_FIELDS])
    outcomes = {}
    for pr in stalled_prs(prs, datetime.now(UTC)):
        try:
            run_gh_text(["pr", "merge", pr, "--disable-auto"])
        except RuntimeError as error:
            outcomes[pr] = str(error)
            continue
        try:
            arm_auto_merge(pr)
        except RuntimeError as error:
            outcomes[pr] = (
                f"auto-merge is now unarmed -- re-arming failed: {error} -- "
                f"run finish_branch.py {pr}"
            )
            continue
        outcomes[pr] = REARMED
    return outcomes
