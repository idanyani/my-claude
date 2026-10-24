"""Find local commits that build on a pull request without being in it.

Every worktree of a repo shares one object store and ref namespace, so a commit made in any sibling
checkout -- a branch with no upstream, a detached HEAD -- is visible from wherever this runs. A
local tip "builds on" the PR when it contains one of the PR's commits; the commits it holds beyond
the PR's head branch would be lost if the PR merged now.
"""

from lib.gh import git_succeeds, run_gh, run_git


def parse_local_tips(for_each_ref: str, worktree_porcelain: str) -> dict[str, str]:
    """Each local tip's label mapped to its OID: every branch, then every detached worktree HEAD.

    Parses `git for-each-ref --format='%(objectname) %(refname:lstrip=2)' refs/heads` and
    `git worktree list --porcelain`. A worktree on a branch is already covered by the branch (and
    one on an unborn branch has no commit), so only detached entries add a tip, labeled by path.
    """
    tips: dict[str, str] = {}
    for line in for_each_ref.splitlines():
        oid, _, branch = line.partition(" ")
        tips[branch] = oid
    for entry in worktree_porcelain.split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in entry.splitlines())
        if "detached" in fields:
            tips[fields["worktree"]] = fields["HEAD"]
    return tips


def commits_missing_from_pr(pr: str) -> tuple[str, dict[str, list[str]]]:
    """The PR's head branch tip on origin, and each local tip that builds on the PR mapped to its
    commits that branch tip lacks.

    The commits are `git rev-list --oneline` lines per tip label; empty when the branch holds them
    all. GitHub adds a pushed commit to the PR seconds after the branch moves, so a merge relying
    on this answer must be pinned to the returned tip.
    """
    view = run_gh(["pr", "view", pr, "--json", "headRefName,commits"])
    # The branch, not the PR head, so a push just made counts; fetching also brings in commits
    # that exist only on the remote (e.g. after an update-branch merge).
    run_git(["fetch", "origin", f"refs/heads/{view['headRefName']}"])
    head = run_git(["rev-parse", "FETCH_HEAD"]).strip()
    tips = parse_local_tips(
        run_git(["for-each-ref", "--format=%(objectname) %(refname:lstrip=2)", "refs/heads"]),
        run_git(["worktree", "list", "--porcelain"]),
    )
    missing = {}
    for label, tip in tips.items():
        builds_on_pr = any(
            git_succeeds(["merge-base", "--is-ancestor", pr_commit["oid"], tip])
            for pr_commit in view["commits"]
        )
        if builds_on_pr:
            commits = run_git(["rev-list", "--oneline", tip, f"^{head}"]).splitlines()
            if commits:
                missing[label] = commits
    return head, missing
