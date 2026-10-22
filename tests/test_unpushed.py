"""`lib.unpushed` against real git repos; only `gh pr view` is faked.

The worktree scenarios cover review fixes made on a second worktree's branch with no upstream and
on a second worktree's detached HEAD.
"""

from pathlib import Path

import pytest
from git_repo import commit, git, publish_pr_head
from lib import unpushed
from lib.unpushed import commits_missing_from_pr, parse_local_tips

PR = "7"
BRANCH = "7-x"


@pytest.fixture
def pr_head(clone: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Open PR #7 from `7-x`, pushed and checked out in `clone`; returns its head."""
    git(clone, "checkout", "-q", "-b", BRANCH, "main")
    head = commit(clone, "implement")
    git(clone, "push", "-q", "-u", "origin", BRANCH)
    publish_pr_head(clone, head, PR)
    view = {"headRefOid": head, "commits": [{"oid": head}]}
    monkeypatch.setattr(unpushed, "run_gh", lambda _args: view)
    return head


def subjects(missing: dict[str, list[str]]) -> dict[str, list[str]]:
    """The `--oneline` lines with their abbreviated OIDs dropped."""
    return {tip: [line.split(" ", 1)[1] for line in lines] for tip, lines in missing.items()}


class TestParseLocalTips:
    def test_labels_branches_by_name_and_detached_heads_by_worktree(self):
        for_each_ref = "aaa main\nbbb 7-x\n"
        porcelain = "\n".join(
            [
                "worktree /repo",
                "HEAD aaa",
                "branch refs/heads/main",
                "",
                "worktree /repo-review",
                "HEAD ccc",
                "detached",
                "",
            ]
        )
        assert parse_local_tips(for_each_ref, porcelain) == {
            "main": "aaa",
            "7-x": "bbb",
            "/repo-review": "ccc",
        }

    def test_keeps_every_label_sharing_a_tip(self):
        porcelain = "worktree /repo-review\nHEAD bbb\ndetached\n"
        assert parse_local_tips("bbb 7-x\nbbb pr7\n", porcelain) == {
            "7-x": "bbb",
            "pr7": "bbb",
            "/repo-review": "bbb",
        }

    def test_skips_a_worktree_on_an_unborn_branch(self):
        # `git worktree add --orphan` lists an all-zero HEAD until its first commit.
        porcelain = "worktree /repo-new\nHEAD " + "0" * 40 + "\nbranch refs/heads/new\n"
        assert parse_local_tips("", porcelain) == {}


class TestCommitsMissingFromPr:
    def test_is_empty_when_the_pr_holds_every_local_commit(self, pr_head):
        assert commits_missing_from_pr(PR) == {}

    def test_reports_an_unpushed_commit_on_the_pr_branch(self, clone, pr_head):
        commit(clone, "fix review finding")
        assert subjects(commits_missing_from_pr(PR)) == {BRANCH: ["fix review finding"]}

    def test_reports_a_commit_on_another_worktrees_branch_with_no_upstream(
        self, clone, pr_head, tmp_path
    ):
        review = tmp_path / "review"
        git(clone, "worktree", "add", "-q", "-b", "pr7", str(review), pr_head)
        commit(review, "fix review finding")
        assert subjects(commits_missing_from_pr(PR)) == {"pr7": ["fix review finding"]}

    def test_reports_a_commit_on_another_worktrees_detached_head(self, clone, pr_head, tmp_path):
        review = tmp_path / "review"
        git(clone, "worktree", "add", "-q", "--detach", str(review), pr_head)
        commit(review, "fix review finding")
        assert subjects(commits_missing_from_pr(PR)) == {str(review): ["fix review finding"]}

    def test_ignores_a_branch_that_does_not_build_on_the_pr(self, clone, pr_head):
        git(clone, "checkout", "-q", "-b", "8-y", "main")
        commit(clone, "unrelated work")
        assert commits_missing_from_pr(PR) == {}
