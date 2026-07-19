import pytest
from lib.copilot_review import (
    COPILOT_REVIEWER,
    find_copilot_review,
    format_review_comments,
    is_unavailable_review,
    poll_decision,
)
from wait_for_copilot_review import parse_args

UNAVAILABLE_BODY = (
    "Copilot was unable to review this pull request because the user who requested "
    "the review has reached their quota limit."
)


def review(login: str, *, id: int = 1, state: str = "COMMENTED", body: str = "") -> dict:
    """A review shaped like the REST `/pulls/{n}/reviews` payload the scripts read."""
    return {"user": {"login": login}, "id": id, "state": state, "body": body}


class TestCopilotIdentity:
    def test_single_reviewer_login_is_the_bot_login(self):
        # Reading reviews via REST (not GraphQL) means the review author and the re-review request
        # share this one `[bot]` login -- there is no unsuffixed variant to reconcile.
        assert COPILOT_REVIEWER == "copilot-pull-request-reviewer[bot]"


class TestFindCopilotReview:
    def test_finds_the_review_posted_under_the_bot_login(self):
        reviews = [
            review("someone-else", body="x"),
            review(COPILOT_REVIEWER, body="y"),
        ]
        assert find_copilot_review(reviews)["body"] == "y"

    def test_returns_the_latest_copilot_review_across_re_reviews(self):
        reviews = [
            review(COPILOT_REVIEWER, id=10, body="first pass"),
            review("human", id=11, body="looks ok"),
            review(COPILOT_REVIEWER, id=12, body="second pass"),
        ]
        assert find_copilot_review(reviews)["id"] == 12

    def test_returns_none_before_copilot_posts(self):
        assert find_copilot_review([review("human", body="")]) is None

    def test_returns_none_for_an_empty_review_list(self):
        assert find_copilot_review([]) is None


class TestIsUnavailableReview:
    def test_detects_the_quota_notice(self):
        assert is_unavailable_review({"body": UNAVAILABLE_BODY}) is True

    def test_is_case_insensitive(self):
        assert is_unavailable_review({"body": UNAVAILABLE_BODY.upper()}) is True

    def test_a_genuine_review_body_is_available(self):
        assert is_unavailable_review({"body": "Consider renaming this variable."}) is False

    def test_an_empty_missing_or_null_body_is_available(self):
        assert is_unavailable_review({"body": ""}) is False
        assert is_unavailable_review({}) is False
        assert is_unavailable_review({"body": None}) is False


class TestPollDecision:
    present = [review(COPILOT_REVIEWER, body="y")]
    unavailable = [review(COPILOT_REVIEWER, body=UNAVAILABLE_BODY)]

    def test_found_as_soon_as_a_genuine_review_is_present(self):
        assert poll_decision(self.present, 0, 300_000) == "found"

    def test_unavailable_when_the_present_review_is_a_quota_notice(self):
        assert poll_decision(self.unavailable, 0, 300_000) == "unavailable"

    def test_continues_while_absent_and_time_remains(self):
        assert poll_decision([], 1_000, 300_000) == "continue"

    def test_times_out_an_absent_review_at_the_cap(self):
        assert poll_decision([], 300_000, 300_000) == "timeout"

    def test_prefers_found_over_timeout_when_the_review_lands_at_the_cap(self):
        assert poll_decision(self.present, 300_000, 300_000) == "found"


def comment(*, path: str = "src/x.py", line=1, start_line=None, body: str = "b"):
    """A comment shaped like the REST `/pulls/{n}/reviews/{review_id}/comments` payload."""
    return {
        "path": path,
        "line": line,
        "start_line": start_line,
        "body": body,
    }


class TestFormatReviewComments:
    def test_renders_path_and_line_range_and_body(self):
        out = format_review_comments(
            [
                comment(
                    path="src/rtl_docx.py",
                    start_line=334,
                    line=338,
                    body="tblPr may be None",
                )
            ]
        )
        assert "src/rtl_docx.py:334-338" in out
        assert "tblPr may be None" in out

    def test_renders_a_single_line_without_a_range(self):
        out = format_review_comments([comment(path="a.py", start_line=None, line=42, body="x")])
        assert "a.py:42" in out
        assert "42-42" not in out

    def test_file_level_comment_renders_as_path_alone(self):
        out = format_review_comments([comment(path="a.py", start_line=None, line=None, body="x")])
        assert "a.py" in out
        assert "a.py:" not in out

    def test_indents_continuation_lines_of_a_multi_line_body_under_the_bullet(self):
        out = format_review_comments([comment(path="a.py", line=5, body="line one\nline two")])
        assert "\n  line one\n  line two" in out

    def test_empty_list_states_there_are_no_inline_comments(self):
        assert "no inline comments" in format_review_comments([]).lower()


class TestWaitParseArgs:
    def test_keeps_the_pr_when_no_timeout_flag_is_given(self):
        assert parse_args(["123"]) == ("123", 300_000)

    def test_reads_an_explicit_timeout(self):
        assert parse_args(["123", "--timeout-seconds", "60"]) == ("123", 60_000)

    def test_rejects_a_missing_pr(self):
        with pytest.raises(ValueError):
            parse_args([])

    def test_rejects_a_non_positive_timeout(self):
        with pytest.raises(ValueError):
            parse_args(["123", "--timeout-seconds", "0"])
