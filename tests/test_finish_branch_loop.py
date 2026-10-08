"""`finish_branch.main`'s wait loop, with the gh calls and sleeps replaced by fakes.

`merge_decision` decides each tick; these tests cover what the loop does with the outcome.
"""

import finish_branch
import pytest
from lib.merge import PrStatus


def test_stops_for_a_person_on_a_pr_behind_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    behind = PrStatus(
        state="OPEN",
        merge_state_status="BEHIND",
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
