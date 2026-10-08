"""Pure helpers for `finish_branch.py`.

Kept separate from the executable so unit tests import the decision logic without running the
script's gh/git side effects.
"""

import json
import re
from dataclasses import dataclass

# The window must hold a full CI --> auto-merge cycle. On gefen-chat/guide (measurements in
# idanyani/my-claude#42) CI took up to ~6 min and push-to-merge took 7-8.5 min when auto-merge
# acted; one PR was still unmerged after 13 min, with auto-merge stalled for an unknown reason, so
# the window leaves margin beyond that.
DEFAULT_TIMEOUT_SECONDS = 1200


@dataclass(frozen=True)
class FinishArgs:
    """Parsed `finish_branch.py` arguments."""

    pr: str
    worktree: bool
    timeout_ms: int


def parse_args(argv: list[str]) -> FinishArgs:
    worktree = "--worktree" in argv
    flag_index = argv.index("--timeout-seconds") if "--timeout-seconds" in argv else -1
    # Drop `--worktree`, plus the `--timeout-seconds` flag and its value only when present;
    # otherwise flag_index is -1 and `flag_index + 1` is 0, which would silently swallow the <pr>
    # positional.
    positional = [
        arg
        for i, arg in enumerate(argv)
        if arg != "--worktree" and (flag_index == -1 or (i != flag_index and i != flag_index + 1))
    ]
    if not positional:
        raise ValueError("usage: finish_branch.py <pr> [--worktree] [--timeout-seconds N]")
    pr = positional[0]

    if flag_index == -1:
        seconds: float = DEFAULT_TIMEOUT_SECONDS
    else:
        raw = argv[flag_index + 1] if flag_index + 1 < len(argv) else None
        try:
            seconds = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            seconds = 0
        if seconds <= 0:
            raise ValueError(f'--timeout-seconds must be a positive number, got "{raw}"')
    return FinishArgs(pr=pr, worktree=worktree, timeout_ms=int(seconds * 1000))


def parse_main_worktree(porcelain: str) -> str:
    """The main checkout's path from `git worktree list --porcelain`.

    Its first entry is always the main worktree. Cleanup runs from there so it survives removing
    the worktree it was invoked in.
    """
    first = porcelain.split("\n")[0]
    if not first.startswith("worktree "):
        raise ValueError("could not determine the main worktree")
    return first[len("worktree ") :]


def parse_worktree_for_branch(porcelain: str, branch: str) -> str | None:
    """Path of the worktree holding `branch` in `git worktree list --porcelain`, or None."""
    path: str | None = None
    for line in porcelain.split("\n"):
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


@dataclass(frozen=True)
class PrStatus:
    """One poll of the PR: its `gh pr view` fields plus the required checks that failed."""

    state: str
    merge_state_status: str
    head_ref_name: str
    head_oid: str
    auto_merge_armed: bool
    failed_checks: tuple[str, ...]


# gh's error for a head with no checks yet, e.g. "no checks reported on the '44-x' branch".
NO_CHECKS_PATTERN = re.compile(r"^no (required )?checks reported on the '")


def parse_required_checks(returncode: int, stdout: str, stderr: str) -> list[dict[str, str]]:
    """The result of `gh pr checks <pr> --required --json name,bucket`.

    With `--json`, pending checks still exit 0. A head with no checks yet -- just after a push or
    an update, before CI attaches -- makes `gh` fail with "no checks reported on the '<branch>'
    branch"; that reads as an empty list (nothing failed), and the
    bounded wait covers CI that never starts.
    """
    if returncode == 0:
        checks: list[dict[str, str]] = json.loads(stdout)
        return checks
    if NO_CHECKS_PATTERN.match(stderr.strip()):
        return []
    raise RuntimeError(f"gh pr checks exited {returncode}: {stderr.strip()}")


# `gh pr checks` buckets after which a check stays red until someone fixes or re-runs it.
FAILED_CHECK_BUCKETS = ("fail", "cancel")


def failed_required_checks(checks: list[dict[str, str]]) -> tuple[str, ...]:
    """Names of the required checks that failed, from `gh pr checks --json name,bucket`."""
    return tuple(check["name"] for check in checks if check["bucket"] in FAILED_CHECK_BUCKETS)


def merge_decision(pr: PrStatus | None, elapsed_ms: float, timeout_ms: float) -> str:
    """Decide one tick of the bounded wait for a PR to merge.

    A terminal GitHub state ends it immediately -- `MERGED` so the caller cleans up, `CLOSED`
    (unmerged) so it aborts rather than delete an unmerged branch. So does any PR that cannot merge
    until a person acts -- a merge conflict (`DIRTY`), auto-merge not armed, a failed required
    check, or `BEHIND` -- since waiting cannot change it. `BEHIND` means the repo requires branches
    to be up to date and another merge left this one out of date -- a setting the workflow keeps
    off (references/git-workflow.md, Background).

    `pr` is None when the poll could not reach GitHub. That says nothing about the PR, so it never
    ends the wait early: one network error must not cost a merge that lands minutes later.

    Otherwise the wait continues until `elapsed_ms` reaches the cap, at which point it times out
    (the caller proceeds; the next start-branch / clean-gone cleans up the deferred merge later).

    Returns one of: "merged", "closed", "conflict", "unarmed", "check_failed", "behind",
    "timeout", "continue".
    """
    if pr is None:
        return "timeout" if elapsed_ms >= timeout_ms else "continue"
    if pr.state == "MERGED":
        return "merged"
    if pr.state == "CLOSED":
        return "closed"
    if pr.merge_state_status == "DIRTY":
        return "conflict"
    if not pr.auto_merge_armed:
        return "unarmed"
    if pr.failed_checks:
        return "check_failed"
    if pr.merge_state_status == "BEHIND":
        return "behind"
    if elapsed_ms >= timeout_ms:
        return "timeout"
    return "continue"


def assert_merged_tip(
    branch: str, local_oid: str, pr_head_oid: str, *, local_is_ancestor: bool
) -> None:
    """Guard before force-deleting the local branch.

    A squash merge leaves the branch "not fully merged" to git, so cleanup must use `git branch
    -D` -- which would also discard a same-named branch carrying unpushed or diverged commits.
    Refuse unless the local tip is contained in the commit GitHub merged (`local_is_ancestor`):
    the merged head may be the local tip itself, or a merge commit GitHub added on top when it
    brought a `BEHIND` branch up to date. Either way `-D` drops nothing that was not shipped.
    """
    if not local_is_ancestor:
        raise ValueError(
            f"local branch {branch} ({local_oid[:7]}) is not contained in the merged PR head "
            f"({pr_head_oid[:7]}) -- it may have unpushed commits; delete it by hand if intended."
        )


def branch_deletion_plan(
    local_oid: str | None, branch: str, pr_head_oid: str, *, local_is_ancestor: bool
) -> str:
    """Decide what cleanup owes the local branch, given its tip (`None` when it no longer exists).

    An absent branch is already cleaned up -- e.g. a merge run from the branch checkout, or a re-run
    of finish-branch -- so it is a no-op, not an error. A present branch is deletable only once
    `assert_merged_tip` confirms GitHub merged everything it holds.

    Returns "absent" or "delete".
    """
    if local_oid is None:
        return "absent"
    assert_merged_tip(branch, local_oid, pr_head_oid, local_is_ancestor=local_is_ancestor)
    return "delete"
