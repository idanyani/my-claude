import pytest
from lib.merge import arm_verdict, parse_args


class TestParseArgs:
    def test_reads_the_pr(self):
        assert parse_args(["123"]) == "123"

    @pytest.mark.parametrize("argv", [[], ["123", "456"]])
    def test_rejects_anything_but_one_pr(self, argv):
        with pytest.raises(ValueError):
            parse_args(argv)


class TestArmVerdict:
    def test_a_merged_pr_is_merged(self):
        # GitHub drops the auto-merge request once a PR merges.
        assert arm_verdict("MERGED", "UNKNOWN", False) == "merged"

    def test_a_closed_pr_is_closed(self):
        assert arm_verdict("CLOSED", "UNKNOWN", False) == "closed"

    @pytest.mark.parametrize("armed", [True, False])
    def test_a_conflict_needs_a_person_whether_or_not_armed(self, armed):
        assert arm_verdict("OPEN", "CONFLICTING", armed) == "conflict"

    def test_an_open_pr_without_auto_merge_is_unarmed(self):
        assert arm_verdict("OPEN", "MERGEABLE", False) == "unarmed"

    def test_an_armed_pr_github_is_still_checking_is_unknown(self):
        assert arm_verdict("OPEN", "UNKNOWN", True) == "unknown"

    def test_an_armed_pr_without_conflicts_is_armed(self):
        assert arm_verdict("OPEN", "MERGEABLE", True) == "armed"
