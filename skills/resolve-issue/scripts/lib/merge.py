"""Pure helpers for `finish_branch.py`.

Kept separate from the executable so unit tests import the decision logic without running the
script's gh/git side effects (mirrors `copilot_review.py`).
"""

from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 300


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


def merge_decision(state: str, elapsed_ms: float, timeout_ms: float) -> str:
    """Decide one tick of the bounded wait for a PR to merge.

    A terminal GitHub state ends it immediately -- `MERGED` so the caller cleans up, `CLOSED`
    (unmerged) so it aborts rather than delete an unmerged branch. Otherwise the wait continues
    until `elapsed_ms` reaches the cap, at which point it times out (the caller proceeds; the next
    start-branch / clean-gone cleans up the deferred merge later).

    Returns one of: "merged", "closed", "timeout", "continue".
    """
    if state == "MERGED":
        return "merged"
    if state == "CLOSED":
        return "closed"
    if elapsed_ms >= timeout_ms:
        return "timeout"
    return "continue"


def assert_merged_tip(branch: str, local_oid: str, pr_head_oid: str) -> None:
    """Guard before force-deleting the local branch.

    A squash merge leaves the branch "not fully merged" to git, so cleanup must use `git branch
    -D` -- which would also discard a same-named branch carrying unpushed or diverged commits.
    Refuse unless the local tip is exactly the commit GitHub merged, so `-D` can only ever drop the
    branch we actually shipped.
    """
    if local_oid != pr_head_oid:
        raise ValueError(
            f"local branch {branch} ({local_oid[:7]}) does not match the merged PR head "
            f"({pr_head_oid[:7]}) -- it may have unpushed commits; delete it by hand if intended."
        )


def branch_deletion_plan(local_oid: str | None, branch: str, pr_head_oid: str) -> str:
    """Decide what cleanup owes the local branch, given its tip (`None` when it no longer exists).

    An absent branch is already cleaned up -- e.g. a merge run from the branch checkout, or a re-run
    of finish-branch -- so it is a no-op, not an error. A present branch is deletable only once
    `assert_merged_tip` confirms it is exactly the commit GitHub merged.

    Returns "absent" or "delete".
    """
    if local_oid is None:
        return "absent"
    assert_merged_tip(branch, local_oid, pr_head_oid)
    return "delete"
