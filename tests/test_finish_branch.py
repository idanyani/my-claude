"""`finish_branch.main`, with the gh and git calls and the sleeps replaced by fakes."""

from collections.abc import Iterator

import finish_branch
import pytest

PR = "7"
ARMED = {"state": "OPEN", "mergeable": "MERGEABLE", "autoMergeRequest": {"mergeMethod": "SQUASH"}}
UNKNOWN = {**ARMED, "mergeable": "UNKNOWN"}
UNARMED = {**ARMED, "autoMergeRequest": None}
CONFLICT = {**ARMED, "mergeable": "CONFLICTING"}
MERGED = {"state": "MERGED", "mergeable": "UNKNOWN", "autoMergeRequest": None}
CLOSED = {"state": "CLOSED", "mergeable": "UNKNOWN", "autoMergeRequest": None}


@pytest.fixture
def git_calls() -> list[list[str]]:
    return []


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, git_calls: list[list[str]]):
    """Run `main` against scripted `gh pr view` results; returns its exit code."""

    def run_git(args: list[str]) -> str:
        git_calls.append(args)
        return "worktree /home/dev/repo\n" if args[:2] == ["worktree", "list"] else ""

    def start(views: list[dict], *flags: str) -> int:
        script: Iterator[dict] = iter(views)
        monkeypatch.setattr(finish_branch, "run_gh", lambda _args: next(script))
        monkeypatch.setattr(finish_branch, "run_git", run_git)
        monkeypatch.setattr(finish_branch.time, "sleep", lambda _seconds: None)
        return finish_branch.main([PR, *flags])

    return start


def returned_to_main(git_calls: list[list[str]]) -> bool:
    return git_calls[-2:] == [["checkout", "main"], ["pull", "--ff-only"]]


def test_returns_to_main_once_auto_merge_is_armed_without_conflicts(run, git_calls):
    assert run([ARMED]) == 0
    assert returned_to_main(git_calls)


def test_returns_to_main_after_a_merge(run, git_calls):
    assert run([MERGED]) == 0
    assert returned_to_main(git_calls)


def test_waits_while_github_computes_mergeability(run):
    assert run([UNKNOWN, UNKNOWN, CONFLICT]) == finish_branch.EXIT_NEEDS_ATTENTION


def test_rechecks_a_request_cleared_by_the_merge(run):
    assert run([UNARMED, MERGED]) == 0


def test_stops_for_a_person_on_a_conflict(run, git_calls, capsys):
    assert run([CONFLICT]) == finish_branch.EXIT_NEEDS_ATTENTION
    assert "conflicts with main" in capsys.readouterr().err
    assert not returned_to_main(git_calls)


def test_stops_for_a_person_when_auto_merge_stays_unarmed(run, capsys):
    assert run([UNARMED] * finish_branch.POLL_LIMIT) == finish_branch.EXIT_NEEDS_ATTENTION
    assert "gh pr merge --auto" in capsys.readouterr().err


def test_proceeds_when_mergeability_stays_unknown(run, git_calls, capsys):
    assert run([UNKNOWN] * finish_branch.POLL_LIMIT) == 0
    assert "gh pr ls" in capsys.readouterr().out
    assert returned_to_main(git_calls)


def test_fails_on_a_pr_closed_without_merging(run, git_calls):
    assert run([CLOSED]) == 1
    assert not returned_to_main(git_calls)


def test_names_the_main_checkout_to_leave_a_worktree_for(run, git_calls, capsys):
    assert run([ARMED], "--worktree") == 0
    assert not returned_to_main(git_calls)
    assert "cd /home/dev/repo" in capsys.readouterr().out
