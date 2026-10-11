"""`lib.sweep` against real git repos.

It decides whether `git branch -D` may drop a local branch, so it runs against an actual commit
graph: a bare `origin` publishing merged heads on `refs/pull/<n>/head` as GitHub does, and a clone
holding the local branches. Only GitHub's list of merged PRs is faked.
"""

import subprocess
from pathlib import Path

import pytest
import start_branch
from lib import sweep
from lib.sweep import DELETED, is_ancestor, parse_gone_branches, parse_worktree_for_branch

PR = "7"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(cwd: Path, message: str) -> str:
    git(cwd, "commit", "--allow-empty", "-q", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def branches(clone: Path) -> set[str]:
    return set(git(clone, "branch", "--format=%(refname:short)").split())


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-q", "-b", "main")
    commit(work, "base")
    git(work, "push", "-q", "-u", "origin", "main")
    monkeypatch.chdir(work)
    return work


def publish_pr_head(clone: Path, oid: str, pr: str = PR) -> None:
    git(clone, "push", "-q", "origin", f"{oid}:refs/pull/{pr}/head")


def gone_branch(clone: Path, branch: str) -> str:
    """A pushed branch whose remote copy was then deleted, as on merge; returns its tip."""
    git(clone, "checkout", "-q", "-b", branch, "main")
    tip = commit(clone, f"work on {branch}")
    git(clone, "push", "-q", "-u", "origin", branch)
    git(clone, "checkout", "-q", "main")
    git(clone, "push", "-q", "origin", "--delete", branch)
    return tip


@pytest.fixture
def merged(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[tuple[str, str]]]:
    """GitHub's merged PRs, by head branch; a branch absent here has none."""
    heads: dict[str, list[tuple[str, str]]] = {}
    monkeypatch.setattr(sweep, "merged_pr_heads", lambda branch: heads.get(branch, []))
    return heads


class TestParseGoneBranches:
    def test_keeps_only_the_branches_whose_upstream_is_gone(self):
        for_each_ref = "\n".join(["main ", "7-x [gone]", "8-y [ahead 1]", "scratch ", ""])
        assert parse_gone_branches(for_each_ref) == ["7-x"]


class TestSweepMergedBranches:
    def test_deletes_a_branch_whose_pr_merged(self, clone, merged):
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        assert sweep.sweep_merged_branches() == {"7-x": DELETED}
        assert branches(clone) == {"main"}

    def test_keeps_a_branch_with_no_merged_pr(self, clone, merged):
        # A PR closed unmerged, or a remote branch deleted by hand, also reads as [gone].
        gone_branch(clone, "7-x")
        assert "no merged PR" in sweep.sweep_merged_branches()["7-x"]
        assert "7-x" in branches(clone)

    def test_keeps_a_branch_holding_commits_the_merge_did_not_contain(self, clone, merged):
        shipped = gone_branch(clone, "7-x")
        publish_pr_head(clone, shipped)
        merged["7-x"] = [(PR, shipped)]
        git(clone, "checkout", "-q", "7-x")
        commit(clone, "unpushed")
        git(clone, "checkout", "-q", "main")
        assert "not in any merged PR" in sweep.sweep_merged_branches()["7-x"]
        assert "7-x" in branches(clone)

    def test_leaves_branches_whose_upstream_exists_or_never_existed(self, clone, merged):
        git(clone, "branch", "scratch")
        assert sweep.sweep_merged_branches() == {}
        assert branches(clone) == {"main", "scratch"}

    def test_removes_the_sibling_worktree_of_a_merged_branch(self, clone, merged, tmp_path):
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        sibling = tmp_path / "work-7"
        git(clone, "worktree", "add", "-q", str(sibling), "7-x")
        assert sweep.sweep_merged_branches() == {"7-x": DELETED}
        assert not sibling.exists()

    def test_keeps_the_worktree_it_runs_in(self, clone, merged, tmp_path, monkeypatch):
        # Removing the sibling worktree the sweep runs from would delete the caller's cwd.
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        sibling = tmp_path / "work-7"
        git(clone, "worktree", "add", "-q", str(sibling), "7-x")
        monkeypatch.chdir(sibling)
        assert "checked out" in sweep.sweep_merged_branches()["7-x"]
        assert sibling.exists()
        assert "7-x" in branches(clone)

    def test_keeps_a_branch_when_github_cannot_be_asked(self, clone, monkeypatch):
        def unreachable(_branch: str) -> list[tuple[str, str]]:
            raise RuntimeError("gh pr list exited 1: connection timed out")

        monkeypatch.setattr(sweep, "merged_pr_heads", unreachable)
        gone_branch(clone, "7-x")
        assert "connection timed out" in sweep.sweep_merged_branches()["7-x"]
        assert "7-x" in branches(clone)


class TestStartBranch:
    def test_deletes_a_merged_branch_before_branching(self, clone, merged):
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        git(clone, "checkout", "-q", "7-x")
        assert start_branch.main(["8", "next"]) == 0
        assert branches(clone) == {"main", "8-next"}


PORCELAIN = "\n".join(
    [
        "worktree /home/dev/tiki",
        "HEAD 1111111111111111111111111111111111111111",
        "branch refs/heads/main",
        "",
        "worktree /home/dev/tiki-116",
        "HEAD 2222222222222222222222222222222222222222",
        "branch refs/heads/116-port-worktree-isolation",
        "",
    ]
)


class TestParseWorktreeForBranch:
    def test_finds_the_worktree_holding_a_branch(self):
        assert (
            parse_worktree_for_branch(PORCELAIN, "116-port-worktree-isolation")
            == "/home/dev/tiki-116"
        )

    def test_returns_none_when_no_worktree_holds_the_branch(self):
        assert parse_worktree_for_branch(PORCELAIN, "999-absent") is None


class TestIsAncestor:
    def test_accepts_a_local_tip_equal_to_the_merged_head(self, clone):
        tip = commit(clone, "work")
        assert is_ancestor(PR, tip, tip)

    def test_accepts_a_head_github_advanced_with_an_update_merge_commit(self, clone):
        tip = commit(clone, "work")
        # Build the update-branch merge commit elsewhere and publish it only on the PR ref, so
        # the clone must fetch it -- as after GitHub's update and the branch's deletion.
        update = commit(clone, "Merge main into branch")
        git(clone, "reset", "-q", "--hard", tip)
        git(clone, "reflog", "expire", "--expire=now", "--all")
        publish_pr_head(clone, update)
        git(clone, "gc", "-q", "--prune=now")
        assert is_ancestor(PR, tip, update)

    def test_refuses_a_local_tip_with_unpushed_commits(self, clone):
        shipped = commit(clone, "work")
        publish_pr_head(clone, shipped)
        unpushed = commit(clone, "unpushed")
        assert not is_ancestor(PR, unpushed, shipped)
