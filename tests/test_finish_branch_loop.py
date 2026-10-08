"""`finish_branch.main`'s wait loop, with the gh calls and sleeps replaced by fakes.

`merge_decision` decides each tick; these tests cover what the loop does with the outcome.
"""

from collections.abc import Iterator

import finish_branch
import pytest
from lib.merge import PrStatus

PR = "7"


def pr(state: str, merge_state_status: str, head_oid: str = "head1") -> PrStatus:
    return PrStatus(
        state=state,
        merge_state_status=merge_state_status,
        head_oid=head_oid,
        auto_merge_armed=state == "OPEN",
        failed_checks=(),
    )


def test_retries_an_update_branch_call_that_failed(monkeypatch: pytest.MonkeyPatch):
    # The failed call never moved the head, so the next poll still sees it BEHIND on head1.
    polls: Iterator[PrStatus] = iter(
        [pr("OPEN", "BEHIND"), pr("OPEN", "BEHIND"), pr("MERGED", "UNKNOWN")]
    )
    update_calls: list[list[str]] = []

    def run_gh_text(args: list[str]) -> str:
        update_calls.append(args)
        if len(update_calls) == 1:
            raise RuntimeError("gh: API rate limit exceeded")
        return ""

    monkeypatch.setattr(finish_branch, "pr_view", lambda _pr: {"headRefName": "7-x"})
    monkeypatch.setattr(finish_branch, "pr_status", lambda _pr, _view: next(polls))
    monkeypatch.setattr(finish_branch, "run_gh_text", run_gh_text)
    monkeypatch.setattr(finish_branch, "clean_up", lambda *_args: None)
    monkeypatch.setattr(finish_branch.time, "sleep", lambda _seconds: None)

    assert finish_branch.main([PR]) == 0
    assert update_calls == [["pr", "update-branch", PR]] * 2


def test_times_out_when_every_update_branch_call_fails(monkeypatch: pytest.MonkeyPatch):
    clock_seconds = [0.0]
    timeout_seconds = 60

    def sleep(seconds: float) -> None:
        clock_seconds[0] += seconds
        # Fail instead of hanging the suite if the wait never ends.
        assert clock_seconds[0] < 10 * timeout_seconds, "the wait outlived its timeout"

    def run_gh_text(_args: list[str]) -> str:
        raise RuntimeError("gh: Resource not accessible by integration")

    monkeypatch.setattr(finish_branch, "pr_view", lambda _pr: {"headRefName": "7-x"})
    monkeypatch.setattr(finish_branch, "pr_status", lambda _pr, _view: pr("OPEN", "BEHIND"))
    monkeypatch.setattr(finish_branch, "run_gh_text", run_gh_text)
    monkeypatch.setattr(finish_branch.time, "monotonic", lambda: clock_seconds[0])
    monkeypatch.setattr(finish_branch.time, "sleep", sleep)

    assert finish_branch.main([PR, "--timeout-seconds", str(timeout_seconds)]) == 2
