import pytest
from lib.branch import branch_name, closes_issue, issue_number, worktree_setup_hint


def test_joins_the_issue_number_with_a_kebab_cased_summary():
    assert branch_name(3, "Telegram ingress and auth") == "3-telegram-ingress-and-auth"


def test_collapses_punctuation_and_trims_stray_separators():
    assert branch_name(7, "  Fix: the (modal) bug!! ") == "7-fix-the-modal-bug"


def test_rejects_a_summary_with_no_alphanumerics():
    with pytest.raises(ValueError):
        branch_name(7, "---")


class TestWorktreeSetupHint:
    def test_a_python_project_calls_for_uv_sync(self):
        assert worktree_setup_hint(["pyproject.toml", "README.md"]) == "uv sync"

    def test_a_node_project_calls_for_pnpm_install(self):
        assert worktree_setup_hint(["package.json", "README.md"]) == "pnpm install"

    def test_python_wins_when_both_project_files_are_present(self):
        assert worktree_setup_hint(["package.json", "pyproject.toml"]) == "uv sync"

    def test_no_known_project_file_means_no_hint(self):
        assert worktree_setup_hint(["README.md"]) is None


class TestIssueNumber:
    def test_reads_the_number_branch_name_puts_first(self):
        assert issue_number(branch_name(105, "require resolves")) == 105

    @pytest.mark.parametrize("branch", ["main", "feature-7", "7x-typo", ""])
    def test_is_none_for_a_branch_not_named_for_an_issue(self, branch):
        assert issue_number(branch) is None


class TestClosesIssue:
    @pytest.mark.parametrize(
        "messages",
        [
            "Implement x\n\nResolves #7\n",
            "Implement x\n\nfixes #7",
            "Implement x\n\nCloses: #7",
            # Cross-repo epics close their sub-issues from another repo.
            "Implement x\n\nResolves idanyani/my-claude#7",
            "Fix review finding\n\nImplement x\n\nResolved #7",
        ],
    )
    def test_accepts_a_github_closing_keyword_for_the_issue(self, messages):
        assert closes_issue(messages, 7)

    @pytest.mark.parametrize(
        "messages",
        [
            "Implement x",
            "Implement x\n\nRefs #7",
            "Implement x\n\nResolves #70",
            "Implement x\n\nResolves #17",
            "Implement x\n\nUnresolves #7",
        ],
    )
    def test_rejects_messages_that_do_not_close_the_issue(self, messages):
        assert not closes_issue(messages, 7)
