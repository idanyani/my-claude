"""`lib.stall` against `gh pr list` JSON shaped like real payloads."""

from datetime import UTC, datetime, timedelta

import pytest
import start_branch
from lib import stall
from lib.stall import (
    CI_START_GRACE_SECONDS,
    MERGED,
    REARMED,
    REFIRED,
    STALL_AFTER_SECONDS,
    green_since,
    reopened_since_head,
    stalled_prs,
    unchecked_prs,
)

ARMED_AT = "2026-10-15T20:53:31Z"
CHECK_DONE_AT = "2026-10-15T20:58:50Z"
CHECK_DONE = datetime(2026, 10, 15, 20, 58, 50, tzinfo=UTC)
CHECK_RUN = {
    "__typename": "CheckRun",
    "completedAt": CHECK_DONE_AT,
    "conclusion": "SUCCESS",
    "name": "ci",
    "startedAt": "2026-10-15T20:53:32Z",
    "status": "COMPLETED",
    "workflowName": "CI",
}
# A real stalled PR at 21:12Z: armed, CLEAN, its only check green for 13 minutes, still open.
STALLED = {
    "number": 235,
    "state": "OPEN",
    "mergeStateStatus": "CLEAN",
    "autoMergeRequest": {"enabledAt": ARMED_AT, "mergeMethod": "SQUASH"},
    "statusCheckRollup": [CHECK_RUN],
}
SNAPSHOT_AT = datetime(2026, 10, 15, 21, 12, tzinfo=UTC)
STALL_AFTER = timedelta(seconds=STALL_AFTER_SECONDS)


class TestGreenSince:
    def test_is_the_last_check_completion(self):
        assert green_since(STALLED) == CHECK_DONE

    def test_is_the_arming_time_when_armed_after_the_checks_went_green(self):
        armed_late = {**STALLED, "autoMergeRequest": {"enabledAt": "2026-10-15T21:05:00Z"}}
        assert green_since(armed_late) == datetime(2026, 10, 15, 21, 5, tzinfo=UTC)

    def test_takes_the_latest_of_several_checks(self):
        later = {**CHECK_RUN, "name": "lint", "completedAt": "2026-10-15T21:00:00Z"}
        pr = {**STALLED, "statusCheckRollup": [CHECK_RUN, later]}
        assert green_since(pr) == datetime(2026, 10, 15, 21, 0, tzinfo=UTC)

    def test_is_none_while_a_check_runs(self):
        running = {**CHECK_RUN, "status": "IN_PROGRESS", "completedAt": None, "conclusion": ""}
        assert green_since({**STALLED, "statusCheckRollup": [CHECK_RUN, running]}) is None

    def test_reads_a_commit_status_by_its_start_time(self):
        status = {
            "__typename": "StatusContext",
            "context": "ci/legacy",
            "state": "SUCCESS",
            "startedAt": "2026-10-15T21:01:00Z",
        }
        pr = {**STALLED, "statusCheckRollup": [CHECK_RUN, status]}
        assert green_since(pr) == datetime(2026, 10, 15, 21, 1, tzinfo=UTC)


class TestStalledPrs:
    def test_finds_the_observed_stall(self):
        assert stalled_prs([STALLED], SNAPSHOT_AT) == ["235"]

    def test_counts_a_pr_green_exactly_the_threshold_as_stalled(self):
        assert stalled_prs([STALLED], CHECK_DONE + STALL_AFTER) == ["235"]

    def test_leaves_a_pr_green_for_less_than_the_threshold(self):
        assert stalled_prs([STALLED], CHECK_DONE + STALL_AFTER - timedelta(seconds=1)) == []

    @pytest.mark.parametrize("merge_state", ["BLOCKED", "BEHIND", "UNSTABLE", "DIRTY", "UNKNOWN"])
    def test_leaves_a_pr_github_does_not_call_clean(self, merge_state):
        assert stalled_prs([{**STALLED, "mergeStateStatus": merge_state}], SNAPSHOT_AT) == []

    def test_leaves_an_unarmed_pr(self):
        assert stalled_prs([{**STALLED, "autoMergeRequest": None}], SNAPSHOT_AT) == []

    def test_leaves_a_pr_whose_checks_still_run(self):
        running = {**CHECK_RUN, "status": "IN_PROGRESS", "completedAt": None}
        assert stalled_prs([{**STALLED, "statusCheckRollup": [running]}], SNAPSHOT_AT) == []

    @pytest.mark.parametrize("merge_method", ["MERGE", "REBASE"])
    def test_leaves_a_pr_armed_with_another_merge_method(self, merge_method):
        # Re-arming arms a squash, so it would override a method the user picked by hand.
        armed = {"enabledAt": ARMED_AT, "mergeMethod": merge_method}
        assert stalled_prs([{**STALLED, "autoMergeRequest": armed}], SNAPSHOT_AT) == []

    def test_leaves_a_pr_that_is_no_longer_open(self):
        assert stalled_prs([{**STALLED, "state": "MERGED"}], SNAPSHOT_AT) == []

    def test_picks_the_stalled_prs_out_of_several(self):
        fresh = {**STALLED, "number": 236, "mergeStateStatus": "BLOCKED"}
        assert stalled_prs([fresh, STALLED], SNAPSHOT_AT) == ["235"]


# A real probe PR, armed as finish_branch.py arms: its push fired no CI, so
# its required check never reported and GitHub reads it BLOCKED.
UNCHECKED = {
    "number": 103,
    "state": "OPEN",
    "mergeStateStatus": "BLOCKED",
    "autoMergeRequest": {"enabledAt": "2026-10-20T07:49:55Z", "mergeMethod": "SQUASH"},
    "statusCheckRollup": [],
    "updatedAt": "2026-10-20T07:49:55Z",
}
UNCHECKED_SINCE = datetime(2026, 10, 20, 7, 49, 55, tzinfo=UTC)
CI_START_GRACE = timedelta(seconds=CI_START_GRACE_SECONDS)
HEAD_COMMITTED_AT = "2026-10-20T07:49:44Z"


def reopen_history(reopened_at: str | None) -> dict:
    """The GraphQL payload `lib.stall` reads a PR's last reopen and head commit from."""
    reopens = [{"createdAt": reopened_at}] if reopened_at else []
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reopened": {"nodes": reopens},
                    "commits": {"nodes": [{"commit": {"committedDate": HEAD_COMMITTED_AT}}]},
                }
            }
        }
    }


class TestReopenedSinceHead:
    def test_is_false_for_a_pr_never_reopened(self):
        assert not reopened_since_head(reopen_history(None))

    def test_is_false_when_the_reopen_predates_the_head_commit(self):
        assert not reopened_since_head(reopen_history("2026-10-20T07:00:00Z"))

    def test_is_true_when_reopened_after_the_head_commit(self):
        assert reopened_since_head(reopen_history("2026-10-20T07:56:00Z"))


def numbers(prs: list[dict]) -> list[int]:
    return [pr["number"] for pr in prs]


class TestUncheckedPrs:
    def test_finds_a_blocked_pr_with_no_checks_past_the_grace(self):
        assert numbers(unchecked_prs([UNCHECKED], UNCHECKED_SINCE + CI_START_GRACE)) == [103]

    def test_leaves_an_unarmed_pr(self):
        # Also BLOCKED with no checks: a PR waiting on a required review in a repo without CI.
        pr = {**UNCHECKED, "autoMergeRequest": None}
        assert unchecked_prs([pr], UNCHECKED_SINCE + CI_START_GRACE) == []

    def test_leaves_a_pr_armed_with_another_merge_method(self):
        pr = {**UNCHECKED, "autoMergeRequest": {"enabledAt": ARMED_AT, "mergeMethod": "REBASE"}}
        assert unchecked_prs([pr], UNCHECKED_SINCE + CI_START_GRACE) == []

    def test_leaves_a_pr_whose_ci_may_still_start(self):
        just_pushed = UNCHECKED_SINCE + CI_START_GRACE - timedelta(seconds=1)
        assert unchecked_prs([UNCHECKED], just_pushed) == []

    def test_leaves_a_pr_with_a_check(self):
        pr = {**UNCHECKED, "statusCheckRollup": [CHECK_RUN]}
        assert unchecked_prs([pr], UNCHECKED_SINCE + CI_START_GRACE) == []

    @pytest.mark.parametrize("merge_state", ["CLEAN", "DRAFT", "DIRTY", "UNKNOWN"])
    def test_leaves_a_pr_not_blocked(self, merge_state):
        # A repo with no required check reads CLEAN with no checks at all; nothing is missing.
        pr = {**UNCHECKED, "mergeStateStatus": merge_state}
        assert unchecked_prs([pr], UNCHECKED_SINCE + CI_START_GRACE) == []

    def test_leaves_a_pr_that_is_no_longer_open(self):
        pr = {**UNCHECKED, "state": "CLOSED"}
        assert unchecked_prs([pr], UNCHECKED_SINCE + CI_START_GRACE) == []


class TestUnstickPrs:
    @pytest.fixture
    def gh_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
        """Every disable and arm call, in order; `gh pr list` returns `prs`."""
        calls: list[list[str]] = []

        def run_gh_text(args: list[str]) -> str:
            calls.append(args)
            return ""

        def arm_auto_merge(pr: str) -> str:
            calls.append(["arm", pr])
            return "Pull request will be automatically merged"

        monkeypatch.setattr(stall, "run_gh_text", run_gh_text)
        monkeypatch.setattr(stall, "arm_auto_merge", arm_auto_merge)
        return calls

    def listing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prs: list[dict],
        state_after: str = "OPEN",
        reopened_at: str | None = None,
    ) -> None:
        """`gh pr list` returns `prs`; `gh pr view` then reads each PR as `state_after`.

        The reopen-history query reports a last reopen at `reopened_at`.
        """

        def run_gh(args: list[str]) -> object:
            if args[0] == "api":
                return reopen_history(reopened_at)
            return prs if args[1] == "list" else {"state": state_after}

        monkeypatch.setattr(stall, "run_gh", run_gh)

    def test_reports_a_merge_when_gh_fails_after_merging(self, monkeypatch, gh_calls):
        # On a CLEAN PR gh merges at once, then can fail deleting a branch a worktree holds.
        def merge_then_fail(_pr: str) -> str:
            raise RuntimeError("gh pr merge exited 1: cannot delete branch used by worktree")

        self.listing(monkeypatch, [STALLED], state_after="MERGED")
        monkeypatch.setattr(stall, "arm_auto_merge", merge_then_fail)
        assert stall.unstick_prs() == {"235": MERGED}

    def test_reports_a_merge_that_landed_before_the_disable(self, monkeypatch, gh_calls):
        def already_merged(_args: list[str]) -> str:
            raise RuntimeError("gh pr merge exited 1: Pull request #235 was already merged")

        self.listing(monkeypatch, [STALLED], state_after="MERGED")
        monkeypatch.setattr(stall, "run_gh_text", already_merged)
        assert stall.unstick_prs() == {"235": MERGED}
        assert gh_calls == []

    def test_disables_then_rearms_a_stalled_pr(self, monkeypatch, gh_calls):
        self.listing(monkeypatch, [STALLED])
        assert stall.unstick_prs() == {"235": REARMED}
        assert gh_calls == [["pr", "merge", "235", "--disable-auto"], ["arm", "235"]]

    def test_touches_nothing_when_no_pr_stalled(self, monkeypatch, gh_calls):
        self.listing(monkeypatch, [{**STALLED, "mergeStateStatus": "BLOCKED"}])
        assert stall.unstick_prs() == {}
        assert gh_calls == []

    def test_reports_a_pr_left_unarmed_when_rearming_fails(self, monkeypatch, gh_calls):
        def refuse(_pr: str) -> str:
            raise RuntimeError("gh pr merge exited 1: GraphQL: something broke")

        self.listing(monkeypatch, [STALLED])
        monkeypatch.setattr(stall, "arm_auto_merge", refuse)
        outcome = stall.unstick_prs()["235"]
        assert "unarmed" in outcome
        assert "something broke" in outcome
        assert "finish_branch.py 235" in outcome

    def test_reports_a_failed_disable_and_skips_the_rearm(self, monkeypatch, gh_calls):
        def refuse(_args: list[str]) -> str:
            raise RuntimeError("gh pr merge exited 1: not allowed")

        self.listing(monkeypatch, [STALLED])
        monkeypatch.setattr(stall, "run_gh_text", refuse)
        assert "not allowed" in stall.unstick_prs()["235"]
        assert gh_calls == []

    def test_reopens_then_rearms_an_unchecked_pr(self, monkeypatch, gh_calls):
        # Closing a PR turns its auto-merge off.
        self.listing(monkeypatch, [UNCHECKED])
        assert stall.unstick_prs() == {"103": REFIRED}
        assert gh_calls == [["pr", "close", "103"], ["pr", "reopen", "103"], ["arm", "103"]]

    def test_reports_rather_than_reopens_again_for_the_same_head(self, monkeypatch, gh_calls):
        # A reopen fires nothing when CI skips the head commit (`[skip ci]`); reopening on every
        # sweep would never end.
        self.listing(monkeypatch, [UNCHECKED], reopened_at="2026-10-20T07:56:00Z")
        outcome = stall.unstick_prs()["103"]
        assert outcome != REFIRED
        assert "reopened" in outcome
        assert gh_calls == []

    def test_reports_a_merge_that_landed_before_the_close(self, monkeypatch, gh_calls):
        def already_merged(_args: list[str]) -> str:
            raise RuntimeError("gh pr close exited 1: Pull request #103 is already merged")

        self.listing(monkeypatch, [UNCHECKED], state_after="MERGED")
        monkeypatch.setattr(stall, "run_gh_text", already_merged)
        assert stall.unstick_prs() == {"103": MERGED}

    def test_reports_a_failed_close_and_skips_the_reopen(self, monkeypatch, gh_calls):
        def refuse(_args: list[str]) -> str:
            raise RuntimeError("gh pr close exited 1: not allowed")

        self.listing(monkeypatch, [UNCHECKED])
        monkeypatch.setattr(stall, "run_gh_text", refuse)
        assert "not allowed" in stall.unstick_prs()["103"]
        assert gh_calls == []

    def test_reports_a_pr_left_unarmed_when_rearming_after_the_reopen_fails(
        self, monkeypatch, gh_calls
    ):
        def refuse(_pr: str) -> str:
            raise RuntimeError("gh pr merge exited 1: GraphQL: something broke")

        self.listing(monkeypatch, [UNCHECKED])
        monkeypatch.setattr(stall, "arm_auto_merge", refuse)
        outcome = stall.unstick_prs()["103"]
        assert "unarmed" in outcome
        assert "something broke" in outcome
        assert "finish_branch.py 103" in outcome

    def test_reports_a_pr_left_closed_when_reopening_fails(self, monkeypatch, gh_calls):
        def refuse_reopen(args: list[str]) -> str:
            gh_calls.append(args)
            if args[1] == "reopen":
                raise RuntimeError("gh pr reopen exited 1: not allowed")
            return ""

        self.listing(monkeypatch, [UNCHECKED])
        monkeypatch.setattr(stall, "run_gh_text", refuse_reopen)
        outcome = stall.unstick_prs()["103"]
        assert "closed" in outcome
        assert "not allowed" in outcome
        assert "gh pr reopen 103" in outcome


class TestStartBranchReport:
    def test_names_each_rearmed_merged_and_failed_pr(self, monkeypatch, capsys):
        outcomes = {
            "235": REARMED,
            "236": MERGED,
            "103": REFIRED,
            "182": "gh pr merge exited 1: not allowed",
        }
        monkeypatch.setattr(start_branch, "unstick_prs", lambda: outcomes)
        start_branch.report_unstick_outcomes()
        out = capsys.readouterr().out
        assert "Re-armed auto-merge on PR #235" in out
        assert "PR #103" in out and "CI" in out
        assert "PR #236 merged" in out
        assert "PR #182" in out and "not allowed" in out

    def test_reports_rather_than_raises_when_github_cannot_be_asked(self, monkeypatch, capsys):
        def unreachable() -> dict[str, str]:
            raise RuntimeError("gh pr list exited 1: connection timed out")

        monkeypatch.setattr(start_branch, "unstick_prs", unreachable)
        start_branch.report_unstick_outcomes()
        assert "connection timed out" in capsys.readouterr().out
