"""`finish_branch.main`'s wait loop, with the gh calls and sleeps replaced by fakes.

`merge_decision` decides each tick; these tests cover what the loop does with the outcome.
"""

import finish_branch
import pytest
from lib.merge import PrStatus


def test_survives_a_poll_that_could_not_reach_github(monkeypatch: pytest.MonkeyPatch):
    merged = PrStatus(
        state="MERGED",
        merge_state_status="UNKNOWN",
        head_ref_name="7-x",
        head_oid="head1",
        auto_merge_armed=False,
        failed_checks=(),
    )
    views = iter([RuntimeError("gh pr view exited 1: read: connection timed out"), None])
    cleaned_up: list[str] = []

    def pr_view(_pr: str) -> dict[str, str]:
        error = next(views)
        if error:
            raise error
        return {"headRefName": "7-x"}

    def clean_up(_pr: str, branch: str, *_args: object) -> None:
        cleaned_up.append(branch)

    monkeypatch.setattr(finish_branch, "pr_view", pr_view)
    monkeypatch.setattr(finish_branch, "pr_status", lambda _pr, _view: merged)
    monkeypatch.setattr(finish_branch, "clean_up", clean_up)
    monkeypatch.setattr(finish_branch.time, "sleep", lambda _seconds: None)

    assert finish_branch.main(["7"]) == 0
    assert cleaned_up == ["7-x"]


def test_stops_for_a_person_on_a_pr_behind_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    behind = PrStatus(
        state="OPEN",
        merge_state_status="BEHIND",
        head_ref_name="7-x",
        head_oid="head1",
        auto_merge_armed=True,
        failed_checks=(),
    )

    def sleep(_seconds: float) -> None:
        raise AssertionError("waited on a PR that cannot merge until a person acts")

    monkeypatch.setattr(finish_branch, "pr_view", lambda _pr: {"headRefName": "7-x"})
    monkeypatch.setattr(finish_branch, "pr_status", lambda _pr, _view: behind)
    monkeypatch.setattr(finish_branch.time, "sleep", sleep)

    assert finish_branch.main(["7"]) == finish_branch.EXIT_NEEDS_ATTENTION
    assert "gh pr update-branch 7" in capsys.readouterr().err
