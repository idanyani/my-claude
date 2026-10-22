"""Re-arm or reopen the user's own armed PRs that GitHub left open.

Stalled: GitHub sometimes leaves an armed PR open after its checks pass, with the PR reading CLEAN;
turning auto-merge off and on again makes GitHub merge it. Re-arming goes through the same
`arm_auto_merge` call finish_branch.py makes, so on a PR gh reads as ready it merges at once. Only
PRs armed as a squash -- the method that call re-arms with -- are touched, so a method picked by
hand is never overridden.

Unchecked: a push can land without firing CI, leaving the PR BLOCKED on a required check that
never reports. Closing and reopening the PR fires CI anew.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from lib.gh import arm_auto_merge, run_gh, run_gh_text

# GitHub merges an armed PR within seconds of its last check passing; both observed stalls
# lasted more than 7 minutes.
STALL_AFTER_SECONDS = 300
# CI attaches a check to a PR within seconds of a push; past this, none is coming.
CI_START_GRACE_SECONDS = 300
REARMED = "re-armed"
REFIRED = "re-fired"
MERGED = "merged"
PR_FIELDS = "number,state,mergeStateStatus,autoMergeRequest,statusCheckRollup,updatedAt"
# A PR's last reopen and its head commit; `gh pr list` exposes neither. gh fills in {owner} and
# {repo} from the current repo.
REOPEN_HISTORY_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reopened: timelineItems(last: 1, itemTypes: [REOPENED_EVENT]) {
        nodes { ... on ReopenedEvent { createdAt } }
      }
      commits(last: 1) { nodes { commit { committedDate } } }
    }
  }
}
"""
REOPEN_HISTORY_FIELDS = [
    "-F",
    "owner={owner}",
    "-F",
    "repo={repo}",
    "-f",
    f"query={REOPEN_HISTORY_QUERY}",
]
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


def _open_and_armed_as_squash(pr: dict[str, Any]) -> bool:
    return (
        pr["state"] == "OPEN"
        and pr["autoMergeRequest"] is not None
        and pr["autoMergeRequest"]["mergeMethod"] == "SQUASH"
    )


def stalled_prs(prs: list[dict[str, Any]], now: datetime) -> list[str]:
    """The numbers of the open, armed, CLEAN PRs that have been green for the stall threshold."""
    stalled = []
    for pr in prs:
        if not _open_and_armed_as_squash(pr) or pr["mergeStateStatus"] != "CLEAN":
            continue
        since = green_since(pr)
        if since is not None and now - since >= timedelta(seconds=STALL_AFTER_SECONDS):
            stalled.append(str(pr["number"]))
    return stalled


def unchecked_prs(prs: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """The open, armed PRs blocked with no check of any kind, untouched past the grace.

    A repo with no required check reads such a PR CLEAN, so it is never picked. Only PRs armed as a
    squash count: arming means the merge waits on nothing but checks, where an unarmed PR may be
    BLOCKED on a review instead, and finish_branch.py already flags a PR it could not arm.
    """
    unchecked = []
    for pr in prs:
        if not _open_and_armed_as_squash(pr) or pr["mergeStateStatus"] != "BLOCKED":
            continue
        if pr["statusCheckRollup"]:
            continue
        untouched = now - datetime.fromisoformat(pr["updatedAt"])
        if untouched >= timedelta(seconds=CI_START_GRACE_SECONDS):
            unchecked.append(pr)
    return unchecked


def reopened_since_head(history: dict[str, Any]) -> bool:
    """Whether the PR was reopened after its head commit, from `REOPEN_HISTORY_QUERY`'s payload."""
    pull_request = history["data"]["repository"]["pullRequest"]
    reopens = pull_request["reopened"]["nodes"]
    if not reopens:
        return False
    head = pull_request["commits"]["nodes"][0]["commit"]
    return datetime.fromisoformat(reopens[0]["createdAt"]) >= datetime.fromisoformat(
        head["committedDate"]
    )


def unstick_prs() -> dict[str, str]:
    """Re-arm each of the user's stalled PRs, and reopen each unchecked one to re-fire its CI.

    Returns each PR acted on mapped to `REARMED`, `REFIRED`, `MERGED`, or what went wrong.
    """
    prs = run_gh(["pr", "list", "--author", "@me", "--state", "open", "--json", PR_FIELDS])
    now = datetime.now(UTC)
    outcomes = {pr: _rearm(pr) for pr in stalled_prs(prs, now)}
    outcomes |= {str(pr["number"]): _refire(pr) for pr in unchecked_prs(prs, now)}
    return outcomes


def _refire(pr: dict[str, Any]) -> str:
    """Close and reopen a PR, which fires its CI anew; return `REFIRED`, `MERGED`, or what went wrong.

    A reopen fires nothing when CI skips the head commit (`[skip ci]`), and the PR would then be
    picked again on every sweep, so each head commit gets one reopen; after that it is reported.
    Closing turns auto-merge off, so the PR is armed again after the reopen.
    """
    number = str(pr["number"])
    history = run_gh(["api", "graphql", *REOPEN_HISTORY_FIELDS, "-F", f"number={number}"])
    if reopened_since_head(history):
        return (
            "it was already reopened for its head commit and still has no check -- CI may skip "
            "that commit; see Troubleshooting in references/git-workflow.md"
        )
    try:
        run_gh_text(["pr", "close", number])
    except RuntimeError as error:
        return MERGED if _merged(number) else str(error)
    try:
        run_gh_text(["pr", "reopen", number])
    except RuntimeError as error:
        return f"the PR is now closed -- reopening failed: {error} -- run gh pr reopen {number}"
    try:
        arm_auto_merge(number)
    except RuntimeError as error:
        return (
            f"CI re-fired but auto-merge is now unarmed -- re-arming failed: {error} -- "
            f"run finish_branch.py {number}"
        )
    return REFIRED


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
