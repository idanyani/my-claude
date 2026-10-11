"""Pure helpers for `finish_branch.py`.

Kept separate from the executable so unit tests import the decision logic without running the
script's gh/git side effects.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinishArgs:
    """Parsed `finish_branch.py` arguments."""

    pr: str
    worktree: bool


def parse_args(argv: list[str]) -> FinishArgs:
    positional = [arg for arg in argv if arg != "--worktree"]
    if len(positional) != 1:
        raise ValueError("usage: finish_branch.py <pr> [--worktree]")
    return FinishArgs(pr=positional[0], worktree="--worktree" in argv)


# Verdicts GitHub may revise within seconds of arming auto-merge: it computes mergeability lazily
# after a push, and it clears the auto-merge request just before the PR reads MERGED.
SETTLING = ("unknown", "unarmed")


def arm_verdict(state: str, mergeable: str, auto_merge_armed: bool) -> str:
    """What GitHub knows about a PR seconds after auto-merge was armed.

    Returns one of "merged", "closed", "conflict", "unarmed", "unknown", "armed".
    """
    if state == "MERGED":
        return "merged"
    if state == "CLOSED":
        return "closed"
    if mergeable == "CONFLICTING":
        return "conflict"
    if not auto_merge_armed:
        return "unarmed"
    if mergeable == "UNKNOWN":
        return "unknown"
    return "armed"
