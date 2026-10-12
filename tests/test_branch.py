import pytest
from lib.branch import branch_name, worktree_setup_hint


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
