"""Delete the local branches whose pull request merged.

Auto-merge's `--delete-branch` removes the remote branch, and `git fetch --prune` then marks the
local branch's upstream `[gone]`. `[gone]` alone does not prove a merge: a PR closed unmerged, or a
remote branch deleted by hand, looks the same. And a squash merge leaves the branch "not fully
merged" to git, so deleting it takes a forced `git branch -D`. So a `[gone]` branch is deleted only
when GitHub lists a merged PR from it whose head contains the local tip -- the sibling worktree
holding it goes first -- and any other `[gone]` branch is kept, with the reason reported.
"""

import subprocess

from lib.gh import run_gh, run_git

DELETED = "deleted"


def parse_gone_branches(for_each_ref: str) -> list[str]:
    """Local branches whose upstream is gone.

    Parses `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads`.
    """
    gone = []
    for line in for_each_ref.splitlines():
        branch, _, track = line.partition(" ")
        if track == "[gone]":
            gone.append(branch)
    return gone


def parse_worktree_for_branch(porcelain: str, branch: str) -> str | None:
    """Path of the worktree holding `branch` in `git worktree list --porcelain`, or None."""
    path: str | None = None
    for line in porcelain.split("\n"):
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


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


def merged_pr_heads(branch: str) -> list[tuple[str, str]]:
    """The number and head OID of each merged PR from `branch`."""
    prs = run_gh(
        ["pr", "list", "--head", branch, "--state", "merged", "--json", "number,headRefOid"]
    )
    return [(str(pr["number"]), pr["headRefOid"]) for pr in prs]


def sweep_merged_branches() -> dict[str, str]:
    """Fetch with `--prune`, then delete each `[gone]` branch whose PR merged.

    Returns each `[gone]` branch mapped to `DELETED` or to the reason it was kept.
    """
    run_git(["fetch", "--prune"])
    for_each_ref = run_git(
        ["for-each-ref", "--format=%(refname:short) %(upstream:track)", "refs/heads"]
    )
    porcelain = run_git(["worktree", "list", "--porcelain"])
    here = run_git(["rev-parse", "--show-toplevel"]).strip()
    outcomes = {}
    for branch in parse_gone_branches(for_each_ref):
        try:
            outcomes[branch] = _sweep_branch(branch, porcelain, here)
        except RuntimeError as error:
            outcomes[branch] = str(error)
    return outcomes


def _sweep_branch(branch: str, porcelain: str, here: str) -> str:
    """Delete one `[gone]` branch if its PR merged; return `DELETED` or why it was kept."""
    worktree = parse_worktree_for_branch(porcelain, branch)
    if worktree == here:
        return "checked out in this worktree"
    heads = merged_pr_heads(branch)
    if not heads:
        return "no merged PR from it -- its remote branch was deleted without a merge"
    tip = run_git(["rev-parse", f"refs/heads/{branch}"]).strip()
    if not any(is_ancestor(pr, tip, head) for pr, head in heads):
        return f"its tip {tip[:7]} is not in any merged PR -- it may hold unpushed commits"
    if worktree:
        run_git(["worktree", "remove", worktree])
    # Forced: a squash merge leaves the branch not-fully-merged to git.
    run_git(["branch", "-D", branch])
    return DELETED
