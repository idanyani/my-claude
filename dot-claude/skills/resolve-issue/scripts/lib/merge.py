"""Pure helpers for `finish_branch.py`.

Kept separate from the executable so unit tests import the decision logic without running the
script's gh/git side effects.
"""


def parse_args(argv: list[str]) -> str:
    """The PR number from `finish_branch.py`'s arguments."""
    if len(argv) != 1:
        raise ValueError("usage: finish_branch.py <pr>")
    return argv[0]


# Verdicts that may change within seconds, so finish_branch.py polls through them: GitHub computes
# mergeability lazily after a push; an unarmed PR is armed on the next poll, and GitHub also clears
# the auto-merge request just before the PR reads MERGED.
SETTLING = ("unknown", "unarmed")


def arm_verdict(state: str, mergeable: str, auto_merge_armed: bool) -> str:
    """What GitHub knows about a PR while finish_branch.py arms and checks it.

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
