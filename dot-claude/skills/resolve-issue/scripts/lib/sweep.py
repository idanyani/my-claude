"""Delete the branches, local and remote, whose pull request merged.

Auto-merge's `--delete-branch` removes the remote branch, and `git fetch --prune` then marks the
local branch's upstream `[gone]`. `[gone]` alone does not prove a merge: a PR closed unmerged, or a
remote branch deleted by hand, looks the same. And a squash merge leaves the branch "not fully
merged" to git, so deleting it takes a forced `git branch -D`. So a `[gone]` branch is deleted only
when GitHub lists a merged PR from it and the local tip holds nothing more: the merged head
contains it, or merging it into `origin/main` changes nothing -- the worktree holding it goes
first -- and any other `[gone]` branch is kept, with the reason reported.

A push made after the merge recreates the deleted remote branch. So a
remote branch with a merged PR and no open one is deleted first when its tip holds nothing more,
by the same test, which leaves its local twin `[gone]` for the same sweep; one that holds more is
kept and reported, since that work never reached `main`.
"""

from lib.gh import git_if_succeeds, git_succeeds, run_gh, run_git

DELETED = "deleted"


def parse_gone_branches(for_each_ref: str) -> list[str]:
    """Local branches whose upstream is gone.

    Parses `git for-each-ref --format='%(refname:lstrip=2) %(upstream:track)' refs/heads`;
    `lstrip=2` rather than `short`, which turns a branch sharing a tag's name into `heads/<name>`.
    """
    gone = []
    for line in for_each_ref.splitlines():
        branch, _, track = line.partition(" ")
        if track == "[gone]":
            gone.append(branch)
    return gone


def parse_main_worktree(porcelain: str) -> str:
    """The main checkout's path from `git worktree list --porcelain`.

    Its first entry is always the main worktree.
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


def is_ancestor(pr: str, local_oid: str, pr_head_oid: str) -> bool:
    """Whether the local tip is contained in the merged PR head.

    A head GitHub advanced with an update-branch merge commit exists only on the remote, so fetch
    it from the PR ref, which outlives the deleted branch.
    """
    if local_oid == pr_head_oid:
        return True
    run_git(["fetch", "origin", f"pull/{pr}/head"])
    return git_succeeds(["merge-base", "--is-ancestor", local_oid, pr_head_oid])


def adds_nothing_to_main(tip: str) -> bool:
    """Whether merging `tip` into `origin/main` leaves its tree unchanged.

    A tree-level test, so it holds however the work reached `main`: squashed, or merged with an
    update-branch or local merge commit. A conflicting merge exits 1, which counts as a change.
    """
    merged = git_if_succeeds(["merge-tree", "--write-tree", "origin/main", tip])
    if merged is None:
        return False
    main_tree = run_git(["rev-parse", "origin/main^{tree}"]).strip()
    return merged.splitlines()[0] == main_tree


def holds_nothing_new(tip: str, heads: list[tuple[str, str]]) -> bool:
    """Whether a merged PR head (number, OID) contains `tip`, or `tip` adds nothing to `main`.

    The ancestry test comes first: `main` may since have changed or reverted the PR's lines, which
    makes a tip still at its merged head read as a change to `main`.
    """
    return any(is_ancestor(pr, tip, head) for pr, head in heads) or adds_nothing_to_main(tip)


def merged_pr_heads(branch: str) -> list[tuple[str, str]]:
    """The number and head OID of each merged PR from `branch`."""
    prs = run_gh(
        ["pr", "list", "--head", branch, "--state", "merged", "--json", "number,headRefOid"]
    )
    return [(str(pr["number"]), pr["headRefOid"]) for pr in prs]


def has_open_pr(branch: str) -> bool:
    """Whether any open PR, by anyone, comes from `branch`; deleting the branch would close it."""
    return bool(run_gh(["pr", "list", "--head", branch, "--state", "open", "--json", "number"]))


def sweep_merged_branches() -> dict[str, str]:
    """Fetch with `--prune`, then delete each remote and `[gone]` local branch whose PR merged.

    Returns each remote branch with a merged PR (as `origin/<branch>`), then each `[gone]` local
    branch, mapped to `DELETED` or to the reason it was kept.
    """
    run_git(["fetch", "--prune"])
    outcomes = _sweep_remote_branches()
    for_each_ref = run_git(
        ["for-each-ref", "--format=%(refname:lstrip=2) %(upstream:track)", "refs/heads"]
    )
    porcelain = run_git(["worktree", "list", "--porcelain"])
    here = run_git(["rev-parse", "--show-toplevel"]).strip()
    for branch in parse_gone_branches(for_each_ref):
        try:
            outcomes[branch] = _sweep_branch(branch, porcelain, here)
        except RuntimeError as error:
            outcomes[branch] = str(error)
    return outcomes


def _sweep_remote_branches() -> dict[str, str]:
    outcomes = {}
    remote_refs = run_git(["for-each-ref", "--format=%(refname:lstrip=3)", "refs/remotes/origin"])
    for branch in remote_refs.splitlines():
        if branch in ("HEAD", "main"):
            continue
        try:
            outcome = _sweep_remote_branch(branch)
        except RuntimeError as error:
            outcome = str(error)
        if outcome is not None:
            outcomes[f"origin/{branch}"] = outcome
    return outcomes


def _sweep_remote_branch(branch: str) -> str | None:
    """Delete one remote branch if its PR merged and it holds nothing new.

    Returns `DELETED`, why it was kept, or None when it has no merged PR or still has an open one.
    """
    heads = merged_pr_heads(branch)
    if not heads or has_open_pr(branch):
        return None
    tip = run_git(["rev-parse", f"refs/remotes/origin/{branch}"]).strip()
    if not holds_nothing_new(tip, heads):
        return (
            f"its tip {tip[:7]} is in no merged PR (#{heads[0][0]} merged) and would change main "
            "-- open a PR for its changes or delete the branch"
        )
    # Also drops the remote-tracking ref, so the local twin reads `[gone]` without a refetch.
    run_git(["push", "origin", "--delete", branch])
    return DELETED


def _sweep_branch(branch: str, porcelain: str, here: str) -> str:
    """Delete one `[gone]` branch if its PR merged; return `DELETED` or why it was kept."""
    worktree = parse_worktree_for_branch(porcelain, branch)
    # git cannot remove the main checkout, and removing the sweep's own worktree would delete the
    # caller's cwd.
    if worktree in (here, parse_main_worktree(porcelain)):
        return f"checked out in {worktree}"
    heads = merged_pr_heads(branch)
    if not heads:
        return "no merged PR from it -- its remote branch was deleted without a merge"
    tip = run_git(["rev-parse", f"refs/heads/{branch}"]).strip()
    if not holds_nothing_new(tip, heads):
        return f"its tip {tip[:7]} is not in any merged PR -- it may hold unpushed commits"
    if worktree:
        run_git(["worktree", "remove", worktree])
    # Forced: a squash merge leaves the branch not-fully-merged to git.
    run_git(["branch", "-D", branch])
    return DELETED
