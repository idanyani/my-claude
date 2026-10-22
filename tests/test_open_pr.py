"""`open_pr` against real git repos; only `gh pr create` is faked.

The push scenario: `main` moved on the remote after the branch was
cut, and the clone never fetched the new tip.
"""

import os
import subprocess
from pathlib import Path

import open_pr
import pytest
from git_repo import commit, git

BRANCH = "7-x"
CLOSING_MESSAGE = "Implement x\n\nResolves #7"
HISTORY_COMMITS = 20
BLOB_BYTES = 10_000
PR_URL = "https://github.com/o/r/pull/7"


@pytest.fixture
def stale_branch(clone: Path, tmp_path: Path) -> Path:
    """`clone` on a one-commit branch whose base `main` the remote has since moved past.

    The history behind the branch is incompressible and larger than the remote accepts in one
    push, so only a push that leaves it out can land.
    """
    for i in range(HISTORY_COMMITS):
        (clone / f"f{i}").write_bytes(os.urandom(BLOB_BYTES))
        git(clone, "add", f"f{i}")
        commit(clone, f"history {i}")
    git(clone, "push", "-q", "origin", "main")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
    commit(other, "another PR merged")
    git(other, "push", "-q", "origin", "main")
    git(tmp_path / "origin.git", "config", "receive.maxInputSize", str(BLOB_BYTES))
    git(clone, "checkout", "-q", "-b", BRANCH)
    commit(clone, CLOSING_MESSAGE)
    return clone


class TestRefusal:
    def test_allows_an_issue_branch_whose_commit_closes_the_issue(self):
        assert open_pr.refusal(BRANCH, [CLOSING_MESSAGE]) is None

    @pytest.mark.parametrize(
        ("branch", "messages"),
        [
            ("", [CLOSING_MESSAGE]),
            ("main", [CLOSING_MESSAGE]),
            (BRANCH, []),
            ("feature-x", [CLOSING_MESSAGE]),
            (BRANCH, ["Implement x"]),
            (BRANCH, [""]),
            ("8-y", [CLOSING_MESSAGE]),
            # `gh pr create --fill` puts only the subjects of several commits in the PR body.
            (BRANCH, ["Fix lint", CLOSING_MESSAGE]),
        ],
        ids=[
            "detached",
            "main",
            "no-commits",
            "not-named-for-an-issue",
            "no-closing-line",
            "empty-message",
            "closes-another-issue",
            "several-commits",
        ],
    )
    def test_refuses(self, branch, messages):
        assert open_pr.refusal(branch, messages)

    def test_names_the_rename_for_a_branch_not_named_for_an_issue(self):
        assert "git branch -m" in open_pr.refusal("feature-x", [CLOSING_MESSAGE])

    def test_counts_an_empty_message_as_a_commit(self):
        assert "no commits" not in open_pr.refusal(BRANCH, [""])


class TestPushBranch:
    def test_fixture_rejects_a_plain_push(self, stale_branch):
        # Keeps the fixture honest: if a plain push lands, the tests below prove nothing.
        with pytest.raises(subprocess.CalledProcessError):
            git(stale_branch, "-c", "push.negotiate=false", "push", "-q", "origin", BRANCH)

    def test_sends_only_what_the_remote_lacks_after_main_moved(self, stale_branch, tmp_path):
        open_pr.push_branch(BRANCH)
        head = git(stale_branch, "rev-parse", "HEAD")
        assert git(tmp_path / "origin.git", "rev-parse", BRANCH) == head

    def test_sets_the_upstream(self, stale_branch):
        open_pr.push_branch(BRANCH)
        assert git(stale_branch, "rev-parse", "--abbrev-ref", "@{upstream}") == f"origin/{BRANCH}"


class TestMain:
    def test_pushes_then_creates_the_pr_and_prints_its_url(
        self, stale_branch, tmp_path, monkeypatch, capsys
    ):
        gh_calls = []

        def run_gh_text(args: list[str]) -> str:
            # The PR can only be created once its branch is on the remote.
            git(tmp_path / "origin.git", "rev-parse", "--verify", BRANCH)
            gh_calls.append(args)
            return PR_URL + "\n"

        monkeypatch.setattr(open_pr, "run_gh_text", run_gh_text)
        assert open_pr.main([]) == 0
        assert gh_calls == [["pr", "create", "--fill"]]
        assert capsys.readouterr().out.strip() == PR_URL

    def test_rejects_arguments(self):
        with pytest.raises(ValueError):
            open_pr.main(["7"])

    def test_refuses_on_main_without_pushing(self, clone, tmp_path):
        commit(clone, "unpublished")
        with pytest.raises(RuntimeError):
            open_pr.main([])
        assert git(tmp_path / "origin.git", "rev-parse", "main") != git(clone, "rev-parse", "HEAD")

    def test_refuses_commits_that_do_not_close_the_issue_without_pushing(
        self, stale_branch, tmp_path
    ):
        git(stale_branch, "commit", "-q", "--amend", "--allow-empty", "-m", "Implement x")
        with pytest.raises(RuntimeError, match="#7"):
            open_pr.main([])
        branches = git(tmp_path / "origin.git", "branch", "--list", BRANCH)
        assert branches == ""
