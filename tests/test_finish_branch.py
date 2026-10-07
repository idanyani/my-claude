"""`finish_branch.is_ancestor` against real git repos.

It decides whether `git branch -D` may drop the local branch, so it runs against an actual commit
graph: a bare `origin` publishing the merged head on `refs/pull/<n>/head` as GitHub does, and a
clone holding the local branch.
"""

import subprocess
from pathlib import Path

import pytest
from finish_branch import is_ancestor

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


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    commit(work, "base")
    monkeypatch.chdir(work)
    return work


def publish_pr_head(clone: Path, oid: str) -> None:
    git(clone, "push", "-q", "origin", f"{oid}:refs/pull/{PR}/head")


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
