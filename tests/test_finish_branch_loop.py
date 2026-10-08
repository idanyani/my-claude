"""`finish_branch.main`'s wait loop, with the gh calls and sleeps replaced by fakes.

`merge_decision` decides each tick; these tests cover what the loop does with the outcome and with
a poll that could not get the PR's status.
"""

import json
from collections.abc import Iterator

import finish_branch
import pytest
from lib.merge import PrStatus

PR = "7"
TIMEOUT_SECONDS = 60
UNREACHABLE = RuntimeError("gh pr view exited 1: read: connection timed out")


def status(state: str = "OPEN", merge_state_status: str = "BLOCKED", armed: bool = True):
    return PrStatus(
        state=state,
        merge_state_status=merge_state_status,
        head_ref_name="7-from-status",
        head_oid="head1",
        auto_merge_armed=armed,
        failed_checks=(),
    )


MERGED = status("MERGED", "UNKNOWN", armed=False)


@pytest.fixture
def cleaned_up() -> list[str]:
    """The branches `main` cleaned up."""
    return []


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, cleaned_up: list[str]):
    """Run `main` against scripted polls: each item is a status, or an error the poll raises."""
    clock_seconds = [0.0]

    def sleep(seconds: float) -> None:
        clock_seconds[0] += seconds
        assert clock_seconds[0] < 10 * TIMEOUT_SECONDS, "the wait outlived its timeout"

    def start(script: Iterator[PrStatus | Exception]) -> int:
        def pr_view(_pr: str) -> PrStatus:
            item = next(script)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(finish_branch, "pr_view", pr_view)
        monkeypatch.setattr(finish_branch, "pr_status", lambda _pr, view: view)
        monkeypatch.setattr(
            finish_branch, "clean_up", lambda _pr, branch, *_args: cleaned_up.append(branch)
        )
        monkeypatch.setattr(finish_branch.time, "monotonic", lambda: clock_seconds[0])
        monkeypatch.setattr(finish_branch.time, "sleep", sleep)
        return finish_branch.main([PR, "--timeout-seconds", str(TIMEOUT_SECONDS)])

    return start


@pytest.mark.parametrize(
    "failure", [UNREACHABLE, json.JSONDecodeError("truncated response", "{", 1)]
)
def test_survives_a_poll_that_could_not_get_the_status(
    run, cleaned_up: list[str], failure: Exception
):
    assert run(iter([status(), failure, MERGED])) == 0
    assert cleaned_up == ["7-from-status"]


def test_fails_fast_when_the_first_poll_errors(run):
    # A bad PR number, a missing gh login, or the wrong repo fails every poll; say so at once.
    with pytest.raises(RuntimeError, match="connection timed out"):
        run(iter([UNREACHABLE]))


def test_reports_github_still_unreachable_at_the_cap(run, capsys: pytest.CaptureFixture[str]):
    def script() -> Iterator[PrStatus | Exception]:
        yield status()
        while True:
            yield UNREACHABLE

    assert run(script()) == 1
    assert "connection timed out" in capsys.readouterr().err


def test_a_failed_poll_does_not_reset_the_unarmed_confirmation(run):
    # A failed poll says nothing about the PR, so the second unarmed sighting still confirms.
    unarmed = status(armed=False)
    assert run(iter([unarmed, UNREACHABLE, unarmed])) == finish_branch.EXIT_NEEDS_ATTENTION


def test_stops_for_a_person_on_a_pr_behind_main(run, capsys: pytest.CaptureFixture[str]):
    assert run(iter([status(merge_state_status="BEHIND")])) == finish_branch.EXIT_NEEDS_ATTENTION
    assert f"gh pr update-branch {PR}" in capsys.readouterr().err
