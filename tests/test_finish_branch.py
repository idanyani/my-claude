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
HEAD = "c0ffee"
REFUSED = RuntimeError("gh pr merge exited 1: GraphQL: Pull Request is not mergeable")


@pytest.fixture
def git_calls() -> list[list[str]]:
    return []


@pytest.fixture
def arm_calls() -> list[tuple[str, str | None]]:
    return []


@pytest.fixture
def run(
    monkeypatch: pytest.MonkeyPatch,
    git_calls: list[list[str]],
    arm_calls: list[tuple[str, str | None]],
):
    """Run `main` against scripted `gh pr view` results; returns its exit code.

    `refusals` is how many arm attempts GitHub refuses before one succeeds; `missing` is what
    `commits_missing_from_pr` finds beyond the head branch's tip, `HEAD`.
    """

    def run_git(args: list[str]) -> str:
        git_calls.append(args)
        return ""

    monkeypatch.setattr(finish_branch, "in_linked_worktree", lambda: False)

    def start(
        views: list[dict], refusals: int = 0, missing: dict[str, list[str]] | None = None
    ) -> int:
        script: Iterator[dict] = iter(views)
        monkeypatch.setattr(
            finish_branch, "commits_missing_from_pr", lambda _pr: (HEAD, missing or {})
        )

        def arm_auto_merge(pr: str, head_oid: str | None = None) -> str:
            arm_calls.append((pr, head_oid))
            if len(arm_calls) <= refusals:
                raise REFUSED
            return "Pull request will be automatically merged"

        monkeypatch.setattr(finish_branch, "run_gh", lambda _args: next(script))
        monkeypatch.setattr(finish_branch, "arm_auto_merge", arm_auto_merge)
        monkeypatch.setattr(finish_branch, "run_git", run_git)
        monkeypatch.setattr(finish_branch.time, "sleep", lambda _seconds: None)
        return finish_branch.main([PR])

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


def test_arms_auto_merge_pinned_to_the_head_checked_for_missing_commits(run, arm_calls):
    assert run([UNARMED, ARMED]) == 0
    assert arm_calls == [(PR, HEAD)]


def test_retries_an_arm_github_refused(run, arm_calls):
    assert run([UNARMED, UNARMED, ARMED], refusals=1) == 0
    assert arm_calls == [(PR, HEAD), (PR, HEAD)]


@pytest.mark.parametrize("view", [ARMED, UNKNOWN, MERGED, CONFLICT, CLOSED])
def test_arms_only_an_open_unarmed_pr(run, arm_calls, view):
    run([view] * finish_branch.POLL_LIMIT)
    assert arm_calls == []


def test_reports_the_last_arm_attempt_not_an_earlier_refusal(run, capsys):
    # GitHub accepted the second attempt, yet the PR never read as armed.
    views = [UNARMED] * finish_branch.POLL_LIMIT
    assert run(views, refusals=1) == finish_branch.EXIT_NEEDS_ATTENTION
    err = capsys.readouterr().err
    assert "automatically merged" in err
    assert "not mergeable" not in err


def test_rechecks_a_request_cleared_by_the_merge(run):
    assert run([UNARMED, MERGED]) == 0


def test_stops_for_a_person_on_a_conflict(run, git_calls, capsys):
    assert run([CONFLICT]) == finish_branch.EXIT_NEEDS_ATTENTION
    assert "conflicts with main" in capsys.readouterr().err
    assert not returned_to_main(git_calls)


def test_stops_for_a_person_naming_why_github_kept_refusing_the_arm(run, capsys):
    views = [UNARMED] * finish_branch.POLL_LIMIT
    assert run(views, refusals=len(views)) == finish_branch.EXIT_NEEDS_ATTENTION
    assert "Pull Request is not mergeable" in capsys.readouterr().err


def test_proceeds_when_mergeability_stays_unknown(run, git_calls, capsys):
    assert run([UNKNOWN] * finish_branch.POLL_LIMIT) == 0
    assert "gh pr ls" in capsys.readouterr().out
    assert returned_to_main(git_calls)


def test_fails_on_a_pr_closed_without_merging(run, git_calls):
    assert run([CLOSED]) == 1
    assert not returned_to_main(git_calls)


def test_stays_in_a_linked_worktree_whose_main_checkout_owns_main(run, git_calls, monkeypatch):
    monkeypatch.setattr(finish_branch, "in_linked_worktree", lambda: True)
    assert run([ARMED]) == 0
    assert git_calls == []


def test_stops_for_a_person_while_local_commits_build_on_the_pr_without_being_in_it(
    run, arm_calls, git_calls, capsys
):
    missing = {"/repo-review": ["1425da7 Fix review finding"]}
    assert run([UNARMED, ARMED], missing=missing) == finish_branch.EXIT_NEEDS_ATTENTION
    assert arm_calls == []
    assert not returned_to_main(git_calls)
    err = capsys.readouterr().err
    assert "/repo-review" in err
    assert "1425da7 Fix review finding" in err


@pytest.mark.parametrize(("view", "code"), [(MERGED, 0), (CLOSED, 1)])
def test_skips_the_missing_commit_check_once_the_pr_is_settled(run, view, code):
    # Re-running after the merge, with follow-up work on the old branch, still reports the merge.
    assert run([view], missing={"7-x": ["abc1234 follow-up"]}) == code
