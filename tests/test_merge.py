import pytest
from lib.merge import (
    DEFAULT_TIMEOUT_SECONDS,
    PrStatus,
    assert_merged_tip,
    branch_deletion_plan,
    failed_required_checks,
    merge_decision,
    parse_args,
    parse_main_worktree,
    parse_required_checks,
    parse_worktree_for_branch,
)

CAP_MS = 300_000


def open_pr(
    merge_state_status: str = "BLOCKED",
    head_oid: str = "head1",
    auto_merge_armed: bool = True,
    failed_checks: tuple[str, ...] = (),
) -> PrStatus:
    return PrStatus(
        state="OPEN",
        merge_state_status=merge_state_status,
        head_oid=head_oid,
        auto_merge_armed=auto_merge_armed,
        failed_checks=failed_checks,
    )


def finished_pr(state: str) -> PrStatus:
    # GitHub drops the auto-merge request once a PR merges or closes.
    return PrStatus(
        state=state,
        merge_state_status="UNKNOWN",
        head_oid="head1",
        auto_merge_armed=False,
        failed_checks=(),
    )


class TestMergeDecision:
    def test_ends_the_wait_as_soon_as_the_pr_is_merged(self):
        merged = finished_pr("MERGED")
        assert merge_decision(merged, None, 0, CAP_MS) == "merged"

    def test_aborts_when_the_pr_is_closed_unmerged(self):
        closed = finished_pr("CLOSED")
        assert merge_decision(closed, None, 0, CAP_MS) == "closed"

    def test_keeps_waiting_while_open_and_time_remains(self):
        assert merge_decision(open_pr(), None, 1_000, CAP_MS) == "continue"

    def test_times_out_an_open_pr_once_the_cap_is_reached(self):
        assert merge_decision(open_pr(), None, CAP_MS, CAP_MS) == "timeout"

    def test_prefers_the_terminal_merged_state_even_at_the_cap(self):
        merged = finished_pr("MERGED")
        assert merge_decision(merged, None, CAP_MS, CAP_MS) == "merged"

    def test_updates_a_pr_that_fell_behind_main(self):
        assert merge_decision(open_pr("BEHIND"), None, 1_000, CAP_MS) == "update"

    def test_updates_a_behind_pr_even_at_the_cap(self):
        # Falling behind is progress on a strict repo -- another PR merged -- not a stall.
        assert merge_decision(open_pr("BEHIND"), None, CAP_MS, CAP_MS) == "update"

    def test_waits_for_an_issued_update_to_land_before_updating_again(self):
        # Until GitHub pushes the update's merge commit, the head is unchanged and the status
        # still reads BEHIND; a second update-branch call then would fail or duplicate work.
        pr = open_pr("BEHIND", head_oid="head1")
        assert merge_decision(pr, "head1", 1_000, CAP_MS) == "continue"

    def test_updates_again_when_main_moves_after_an_earlier_update(self):
        pr = open_pr("BEHIND", head_oid="head2")
        assert merge_decision(pr, "head1", 1_000, CAP_MS) == "update"

    def test_stops_on_a_merge_conflict(self):
        assert merge_decision(open_pr("DIRTY"), None, 1_000, CAP_MS) == "conflict"

    def test_stops_when_auto_merge_is_not_armed(self):
        pr = open_pr(auto_merge_armed=False)
        assert merge_decision(pr, None, 1_000, CAP_MS) == "unarmed"

    def test_stops_when_a_required_check_failed(self):
        pr = open_pr(failed_checks=("verify",))
        assert merge_decision(pr, None, 1_000, CAP_MS) == "check_failed"

    def test_does_not_update_a_behind_pr_whose_required_check_failed(self):
        # An update would spend a CI run on a PR that cannot merge until someone fixes it.
        pr = open_pr("BEHIND", failed_checks=("verify",))
        assert merge_decision(pr, None, 1_000, CAP_MS) == "check_failed"

    def test_does_not_update_a_behind_pr_without_auto_merge(self):
        pr = open_pr("BEHIND", auto_merge_armed=False)
        assert merge_decision(pr, None, 1_000, CAP_MS) == "unarmed"

    def test_keeps_waiting_while_required_checks_are_pending(self):
        assert merge_decision(open_pr(failed_checks=()), None, 1_000, CAP_MS) == "continue"


class TestFailedRequiredChecks:
    def test_names_the_failed_and_cancelled_checks(self):
        checks = [
            {"name": "verify", "bucket": "fail"},
            {"name": "lint", "bucket": "cancel"},
        ]
        assert failed_required_checks(checks) == ("verify", "lint")

    @pytest.mark.parametrize("bucket", ["pass", "pending", "skipping"])
    def test_ignores_checks_that_do_not_block_the_merge_for_good(self, bucket):
        assert failed_required_checks([{"name": "verify", "bucket": bucket}]) == ()

    def test_treats_no_checks_yet_as_nothing_failed(self):
        assert failed_required_checks([]) == ()


class TestParseRequiredChecks:
    def test_reads_the_json_of_a_completed_run(self):
        stdout = '[{"bucket":"pass","name":"verify"}]'
        assert parse_required_checks(0, stdout, "") == [{"bucket": "pass", "name": "verify"}]

    def test_treats_a_head_with_no_checks_yet_as_an_empty_list(self):
        stderr = "no checks reported on the '44-stop-on-unmergeable-pr' branch"
        assert parse_required_checks(1, "", stderr) == []

    def test_raises_on_any_other_failure(self):
        with pytest.raises(RuntimeError, match="HTTP 502"):
            parse_required_checks(1, "", "HTTP 502: Bad Gateway")

    def test_keeps_the_pr_and_defaults_with_no_flags(self):
        args = parse_args(["123"])
        assert (args.pr, args.timeout_ms) == ("123", DEFAULT_TIMEOUT_SECONDS * 1000)

    def test_reads_an_explicit_timeout(self):
        args = parse_args(["123", "--timeout-seconds", "60"])
        assert (args.pr, args.timeout_ms) == ("123", 60_000)

    def test_defaults_worktree_off_when_the_flag_is_absent(self):
        assert parse_args(["123"]).worktree is False

    @pytest.mark.parametrize(
        "argv",
        [
            ["123", "--worktree", "--timeout-seconds", "60"],
            ["123", "--timeout-seconds", "60", "--worktree"],
        ],
    )
    def test_reads_worktree_and_an_explicit_timeout_in_any_order(self, argv):
        args = parse_args(argv)
        assert (args.pr, args.worktree, args.timeout_ms) == ("123", True, 60_000)

    def test_keeps_the_pr_positional_when_only_timeout_is_given(self):
        # Regression guard: with no flag, flag_index is -1 and a naive filter on flag_index + 1
        # (== 0) swallows the <pr> positional.
        args = parse_args(["123", "--timeout-seconds", "60"])
        assert args.pr == "123"

    def test_rejects_a_missing_pr(self):
        with pytest.raises(ValueError):
            parse_args([])

    def test_rejects_flags_alone_without_a_pr(self):
        with pytest.raises(ValueError):
            parse_args(["--worktree"])

    def test_rejects_a_non_positive_timeout(self):
        with pytest.raises(ValueError):
            parse_args(["123", "--timeout-seconds", "0"])


class TestAssertMergedTip:
    def test_passes_when_the_local_tip_is_contained_in_the_merged_pr_head(self):
        assert_merged_tip("3-fix", "abc1234def", "fed4321cba", local_is_ancestor=True)

    def test_refuses_to_force_delete_a_diverged_branch(self):
        with pytest.raises(ValueError, match="unpushed"):
            assert_merged_tip("3-fix", "aaaaaaa1111", "bbbbbbb2222", local_is_ancestor=False)


class TestBranchDeletionPlan:
    def test_an_absent_branch_is_already_cleaned_up(self):
        assert branch_deletion_plan(None, "3-fix", "abc1234", local_is_ancestor=False) == "absent"

    def test_a_contained_branch_is_deletable(self):
        assert (
            branch_deletion_plan("abc1234", "3-fix", "def5678", local_is_ancestor=True) == "delete"
        )

    def test_a_diverged_present_branch_raises(self):
        with pytest.raises(ValueError, match="unpushed"):
            branch_deletion_plan("aaaa", "3-fix", "bbbb", local_is_ancestor=False)


PORCELAIN = "\n".join(
    [
        "worktree /home/dev/tiki",
        "HEAD 1111111111111111111111111111111111111111",
        "branch refs/heads/main",
        "",
        "worktree /home/dev/tiki-116",
        "HEAD 2222222222222222222222222222222222222222",
        "branch refs/heads/116-port-worktree-isolation",
        "",
    ]
)


class TestParseMainWorktree:
    def test_returns_the_first_worktrees_path(self):
        assert parse_main_worktree(PORCELAIN) == "/home/dev/tiki"

    def test_raises_when_there_is_no_worktree_entry(self):
        with pytest.raises(ValueError):
            parse_main_worktree("")


class TestParseWorktreeForBranch:
    def test_finds_the_worktree_holding_a_branch(self):
        assert (
            parse_worktree_for_branch(PORCELAIN, "116-port-worktree-isolation")
            == "/home/dev/tiki-116"
        )

    def test_returns_none_when_no_worktree_holds_the_branch(self):
        assert parse_worktree_for_branch(PORCELAIN, "999-absent") is None
