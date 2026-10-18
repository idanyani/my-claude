"""`lib.sweep` against real git repos.

It decides whether `git branch -D` may drop a local branch, so it runs against an actual commit
graph: a bare `origin` publishing merged heads on `refs/pull/<n>/head` as GitHub does, and a clone
holding the local branches. Only GitHub's lists of PRs are faked.
"""

from pathlib import Path

import git_repo
import pytest
import start_branch
from git_repo import commit, git
from lib import gh, sweep
from lib.sweep import (
    DELETED,
    adds_nothing_to_main,
    is_ancestor,
    parse_gone_branches,
    parse_main_worktree,
    parse_worktree_for_branch,
)

PR = "7"


def exclude_file(clone: Path) -> Path:
    return clone / ".git" / "info" / "exclude"


def branches(clone: Path) -> set[str]:
    return set(git(clone, "branch", "--format=%(refname:short)").split())


def publish_pr_head(clone: Path, oid: str, pr: str = PR) -> None:
    git_repo.publish_pr_head(clone, oid, pr)


def gone_branch(clone: Path, branch: str) -> str:
    """A pushed branch whose remote copy was then deleted, as on merge; returns its tip."""
    git(clone, "checkout", "-q", "-b", branch, "main")
    tip = commit(clone, f"work on {branch}")
    git(clone, "push", "-q", "-u", "origin", branch)
    git(clone, "checkout", "-q", "main")
    git(clone, "push", "-q", "origin", "--delete", branch)
    return tip


def commit_file(clone: Path, name: str, content: str) -> str:
    (clone / name).write_text(content)
    git(clone, "add", name)
    return commit(clone, f"write {name}")


def remote_branches(clone: Path) -> set[str]:
    return set(git(clone, "ls-remote", "--heads", "origin").split()[1::2])


def recreated_branch(clone: Path, branch: str) -> str:
    """A PR branch squash-merged while `main` moved, then recreated by pushing a merge of `main`.

    Reproduces idanyani/my-claude#97: the merge of the pre-squash `main` is pushed after GitHub
    deleted the branch. Returns the PR head GitHub merged.
    """
    git(clone, "checkout", "-q", "-b", branch, "main")
    head = commit_file(clone, "feature.txt", "feature\n")
    git(clone, "push", "-q", "-u", "origin", branch)
    git(clone, "checkout", "-q", "main")
    other_pr = commit_file(clone, "other.txt", "another PR\n")
    git(clone, "checkout", "-q", head, "--", "feature.txt")
    commit(clone, "squash of the PR")
    git(clone, "push", "-q", "origin", "main")
    git(clone, "push", "-q", "origin", "--delete", branch)
    git(clone, "checkout", "-q", branch)
    git(clone, "merge", "-q", "--no-edit", other_pr)
    git(clone, "push", "-q", "origin", branch)
    git(clone, "checkout", "-q", "main")
    publish_pr_head(clone, head)
    return head


@pytest.fixture(autouse=True)
def my_prs(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[tuple[str, str]]]:
    """The number and state of each of the user's PRs, by head branch; absent means none."""
    states: dict[str, list[tuple[str, str]]] = {}
    monkeypatch.setattr(sweep, "my_pr_states", lambda branch: states.get(branch, []))
    return states


@pytest.fixture(autouse=True)
def no_stalled_prs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep `start_branch.main` off GitHub; `test_stall.py` covers the re-arm."""
    monkeypatch.setattr(start_branch, "rearm_stalled_prs", dict)


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
        commit_file(clone, "unpushed.txt", "unpushed\n")
        git(clone, "checkout", "-q", "main")
        assert "not in any merged PR" in sweep.sweep_merged_branches()["7-x"]
        assert "7-x" in branches(clone)

    def test_deletes_a_branch_whose_tip_adds_nothing_to_main(self, clone, merged):
        # A local merge of `main` after the squash-merge is in no PR head, yet holds no work.
        head = recreated_branch(clone, "7-x")
        git(clone, "push", "-q", "origin", "--delete", "7-x")
        merged["7-x"] = [(PR, head)]
        assert sweep.sweep_merged_branches() == {"7-x": DELETED}
        assert branches(clone) == {"main"}

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

    def test_keeps_the_branch_checked_out_in_the_main_checkout(
        self, clone, merged, tmp_path, monkeypatch
    ):
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        git(clone, "checkout", "-q", "7-x")
        sibling = tmp_path / "work-8"
        git(clone, "worktree", "add", "-q", "-b", "8-y", str(sibling), "main")
        monkeypatch.chdir(sibling)
        assert sweep.sweep_merged_branches()["7-x"] == f"checked out in {clone}"

    def test_deletes_a_merged_branch_that_shares_a_tags_name(self, clone, merged):
        tip = gone_branch(clone, "v1")
        git(clone, "tag", "v1", "main")
        publish_pr_head(clone, tip)
        merged["v1"] = [(PR, tip)]
        assert sweep.sweep_merged_branches() == {"v1": DELETED}

    def test_keeps_a_branch_when_github_cannot_be_asked(self, clone, monkeypatch):
        def unreachable(_branch: str) -> list[tuple[str, str]]:
            raise RuntimeError("gh pr list exited 1: connection timed out")

        monkeypatch.setattr(sweep, "merged_pr_heads", unreachable)
        gone_branch(clone, "7-x")
        assert "connection timed out" in sweep.sweep_merged_branches()["7-x"]
        assert "7-x" in branches(clone)


class TestSweepRecreatedRemoteBranches:
    def test_deletes_a_remote_branch_recreated_after_the_merge_and_its_local_twin(
        self, clone, merged, my_prs
    ):
        head = recreated_branch(clone, "7-x")
        merged["7-x"] = [(PR, head)]
        my_prs["7-x"] = [(PR, "MERGED")]
        assert sweep.sweep_merged_branches() == {"origin/7-x": DELETED, "7-x": DELETED}
        assert remote_branches(clone) == {"refs/heads/main"}
        assert branches(clone) == {"main"}

    def test_keeps_a_recreated_remote_branch_holding_work(self, clone, merged, my_prs):
        head = recreated_branch(clone, "7-x")
        git(clone, "checkout", "-q", "7-x")
        commit_file(clone, "late.txt", "pushed after the merge\n")
        git(clone, "push", "-q", "origin", "7-x")
        git(clone, "checkout", "-q", "main")
        merged["7-x"] = [(PR, head)]
        my_prs["7-x"] = [(PR, "MERGED")]
        assert f"PR #{PR}" in sweep.sweep_merged_branches()["origin/7-x"]
        assert "refs/heads/7-x" in remote_branches(clone)

    @pytest.mark.parametrize("states", [[], [(PR, "MERGED"), ("9", "OPEN")], [(PR, "CLOSED")]])
    def test_leaves_a_remote_branch_without_a_settled_merged_pr(self, clone, my_prs, states):
        recreated_branch(clone, "7-x")
        my_prs["7-x"] = states
        assert "origin/7-x" not in sweep.sweep_merged_branches()
        assert "refs/heads/7-x" in remote_branches(clone)

    def test_reports_a_remote_branch_github_cannot_be_asked_about(self, clone, monkeypatch):
        def unreachable(_branch: str) -> list[tuple[str, str]]:
            raise RuntimeError("gh pr list exited 1: connection timed out")

        recreated_branch(clone, "7-x")
        monkeypatch.setattr(sweep, "my_pr_states", unreachable)
        assert "connection timed out" in sweep.sweep_merged_branches()["origin/7-x"]
        assert "refs/heads/7-x" in remote_branches(clone)


class TestAddsNothingToMain:
    def test_accepts_a_tip_main_already_holds(self, clone):
        assert adds_nothing_to_main(git(clone, "rev-parse", "HEAD"))

    def test_refuses_a_tip_with_changes(self, clone):
        git(clone, "checkout", "-q", "-b", "7-x")
        assert not adds_nothing_to_main(commit_file(clone, "new.txt", "new\n"))

    def test_refuses_a_tip_that_conflicts_with_main(self, clone):
        commit_file(clone, "shared.txt", "base\n")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "checkout", "-q", "-b", "7-x")
        tip = commit_file(clone, "shared.txt", "branch\n")
        git(clone, "checkout", "-q", "main")
        commit_file(clone, "shared.txt", "main\n")
        git(clone, "push", "-q", "origin", "main")
        assert not adds_nothing_to_main(tip)


class TestStartBranch:
    def test_reports_a_deleted_recreated_remote_branch(self, clone, merged, my_prs, capsys):
        head = recreated_branch(clone, "7-x")
        merged["7-x"] = [(PR, head)]
        my_prs["7-x"] = [(PR, "MERGED")]
        assert start_branch.main(["8", "next"]) == 0
        assert "Deleted merged branch origin/7-x" in capsys.readouterr().out
        assert remote_branches(clone) == {"refs/heads/main"}

    def test_deletes_a_merged_branch_before_branching(self, clone, merged):
        tip = gone_branch(clone, "7-x")
        publish_pr_head(clone, tip)
        merged["7-x"] = [(PR, tip)]
        git(clone, "checkout", "-q", "7-x")
        assert start_branch.main(["8", "next"]) == 0
        assert branches(clone) == {"main", "8-next"}

    def test_refuses_a_dirty_main_checkout_when_branching_in_place(self, clone, merged):
        (clone / "stray.txt").write_text("uncommitted\n")
        with pytest.raises(RuntimeError, match="dirty"):
            start_branch.main(["8", "next"])

    def test_is_not_blocked_by_claude_code_worktrees_in_the_main_checkout(self, clone, merged):
        git(clone, "worktree", "add", "-q", "-b", "worktree-9", ".claude/worktrees/9", "main")
        assert start_branch.main(["8", "next"]) == 0


class TestStartBranchInLinkedWorktree:
    """A worktree Claude Code created (EnterWorktree, subagent isolation) on its placeholder branch."""

    @pytest.fixture
    def linked(self, clone, merged, tmp_path, monkeypatch) -> Path:
        # Leave local `main` behind origin/main, so a branch based on the local ref is detectable.
        commit(clone, "ahead")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "reset", "-q", "--hard", "HEAD~1")
        worktree = clone / ".claude" / "worktrees" / "8"
        git(clone, "worktree", "add", "-q", "-b", "worktree-8", str(worktree), "main")
        monkeypatch.chdir(worktree)
        return worktree

    def test_branches_from_origin_main(self, clone, linked):
        assert start_branch.main(["8", "next"]) == 0
        assert git(linked, "branch", "--show-current") == "8-next"
        assert git(linked, "rev-parse", "HEAD") == git(clone, "rev-parse", "origin/main")

    def test_leaves_the_branch_without_an_upstream_until_it_is_pushed(self, linked):
        assert start_branch.main(["8", "next"]) == 0
        assert git(linked, "for-each-ref", "--format=%(upstream)", "refs/heads/8-next") == ""

    def test_drops_the_empty_placeholder_branch(self, clone, linked):
        assert start_branch.main(["8", "next"]) == 0
        assert "worktree-8" not in branches(clone)

    def test_keeps_a_placeholder_branch_holding_commits(self, clone, linked, capsys):
        commit(linked, "work on the placeholder")
        assert start_branch.main(["8", "next"]) == 0
        assert "worktree-8" in branches(clone)
        assert "Kept branch worktree-8" in capsys.readouterr().out

    def test_ignores_a_dirty_main_checkout(self, clone, linked):
        (clone / "unrelated.txt").write_text("another session's work in progress\n")
        assert start_branch.main(["8", "next"]) == 0

    def test_refuses_a_dirty_worktree(self, linked):
        (linked / "stray.txt").write_text("uncommitted\n")
        with pytest.raises(RuntimeError, match="dirty"):
            start_branch.main(["8", "next"])

    def test_keeps_the_worktrees_out_of_the_main_checkouts_status(self, clone, linked):
        assert start_branch.main(["8", "next"]) == 0
        assert git(clone, "status", "--porcelain") == ""

    def test_leaves_the_exclude_file_alone_when_the_repo_ignores_worktrees(
        self, clone, linked, monkeypatch
    ):
        git(linked, "reset", "-q", "--hard", "origin/main")
        (linked / ".gitignore").write_text(".claude/worktrees/\n")
        git(linked, "add", ".gitignore")
        commit(linked, "ignore worktrees")
        git(linked, "push", "-q", "origin", "HEAD:main")
        (linked / "sub").mkdir()
        monkeypatch.chdir(linked / "sub")
        assert start_branch.main(["8", "next"]) == 0
        assert ".claude/worktrees/" not in exclude_file(clone).read_text()

    def test_keeps_a_branch_claude_code_did_not_create(self, clone, merged, monkeypatch):
        # Every commit of `7-real` is on origin/main, so `git branch -d` alone would delete it.
        worktree = clone / ".claude" / "worktrees" / "7"
        git(clone, "worktree", "add", "-q", "-b", "7-real", str(worktree), "main")
        monkeypatch.chdir(worktree)
        assert start_branch.main(["8", "next"]) == 0
        assert "7-real" in branches(clone)


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


class TestParseMainWorktree:
    def test_returns_the_first_worktrees_path(self):
        assert parse_main_worktree(PORCELAIN) == "/home/dev/tiki"

    def test_raises_when_there_is_no_worktree_entry(self):
        with pytest.raises(ValueError):
            parse_main_worktree("")


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


class TestInLinkedWorktree:
    @pytest.mark.parametrize(
        ("rev_parse", "linked"),
        [
            ("/home/my repos/p/.git/worktrees/8\n/home/my repos/p/.git\n", True),
            ("/home/my repos/p/.git\n/home/my repos/p/.git\n", False),
        ],
    )
    def test_compares_the_git_dirs_of_a_path_with_spaces(self, monkeypatch, rev_parse, linked):
        monkeypatch.setattr(gh, "run_git", lambda _args: rev_parse)
        assert gh.in_linked_worktree() is linked
