"""Find local commits that build on a pull request without being in it.

Every worktree of a repo shares one object store and ref namespace, so a commit made in any sibling
checkout -- a branch with no upstream, a detached HEAD -- is visible from wherever this runs. A
local tip "builds on" the PR when it contains one of the PR's commits; the commits it holds beyond
the PR head would be lost if the PR merged now.
"""

from lib.gh import git_succeeds, run_gh, run_git


def parse_local_tips(for_each_ref: str, worktree_porcelain: str) -> dict[str, str]:
    """Each local tip's OID mapped to a label: its branch name, else the worktree holding it.

    Parses `git for-each-ref --format='%(objectname) %(refname:lstrip=2)' refs/heads` and
    `git worktree list --porcelain`; the latter adds the detached HEADs no branch names.
    """
    tips: dict[str, str] = {}
    for line in for_each_ref.splitlines():
        oid, _, branch = line.partition(" ")
        tips[oid] = branch
    worktree = ""
    for line in worktree_porcelain.splitlines():
        if line.startswith("worktree "):
            worktree = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            tips.setdefault(line[len("HEAD ") :], worktree)
    return tips


def commits_missing_from_pr(pr: str) -> dict[str, list[str]]:
    """Each local tip that builds on the PR mapped to its commits the PR head lacks.

    Returns `git rev-list --oneline` lines per tip label; empty when the PR holds them all.
    """
    view = run_gh(["pr", "view", pr, "--json", "headRefOid,commits"])
    head = view["headRefOid"]
    # The head may exist only on the remote, e.g. after GitHub's update-branch merge.
    run_git(["fetch", "origin", f"pull/{pr}/head"])
    tips = parse_local_tips(
        run_git(["for-each-ref", "--format=%(objectname) %(refname:lstrip=2)", "refs/heads"]),
        run_git(["worktree", "list", "--porcelain"]),
    )
    missing = {}
    for tip, label in tips.items():
        builds_on_pr = any(
            git_succeeds(["merge-base", "--is-ancestor", pr_commit["oid"], tip])
            for pr_commit in view["commits"]
        )
        if builds_on_pr:
            commits = run_git(["rev-list", "--oneline", tip, f"^{head}"]).splitlines()
            if commits:
                missing[label] = commits
    return missing
