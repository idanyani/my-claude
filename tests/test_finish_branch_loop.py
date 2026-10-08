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
