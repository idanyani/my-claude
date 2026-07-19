import pytest
from lib.merge import (
    assert_merged_tip,
    branch_deletion_plan,
    merge_decision,
    parse_args,
    parse_main_worktree,
    parse_worktree_for_branch,
)


class TestMergeDecision:
    def test_ends_the_wait_as_soon_as_the_pr_is_merged(self):
        assert merge_decision("MERGED", 0, 300_000) == "merged"

    def test_aborts_when_the_pr_is_closed_unmerged(self):
        assert merge_decision("CLOSED", 0, 300_000) == "closed"

    def test_keeps_waiting_while_open_and_time_remains(self):
        assert merge_decision("OPEN", 1_000, 300_000) == "continue"

    def test_times_out_an_open_pr_once_the_cap_is_reached(self):
        assert merge_decision("OPEN", 300_000, 300_000) == "timeout"

    def test_prefers_the_terminal_merged_state_even_at_the_cap(self):
        assert merge_decision("MERGED", 300_000, 300_000) == "merged"


class TestParseArgs:
    def test_keeps_the_pr_and_defaults_with_no_flags(self):
        args = parse_args(["123"])
        assert (args.pr, args.timeout_ms) == ("123", 300_000)

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
    def test_passes_when_the_local_tip_is_exactly_the_merged_pr_head(self):
        assert_merged_tip("3-fix", "abc1234def", "abc1234def")

    def test_refuses_to_force_delete_a_diverged_branch(self):
        with pytest.raises(ValueError, match="unpushed"):
            assert_merged_tip("3-fix", "aaaaaaa1111", "bbbbbbb2222")


class TestBranchDeletionPlan:
    def test_an_absent_branch_is_already_cleaned_up(self):
        assert branch_deletion_plan(None, "3-fix", "abc1234") == "absent"

    def test_a_matching_branch_is_deletable(self):
        assert branch_deletion_plan("abc1234", "3-fix", "abc1234") == "delete"

    def test_a_diverged_present_branch_raises(self):
        with pytest.raises(ValueError, match="unpushed"):
            branch_deletion_plan("aaaa", "3-fix", "bbbb")


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
