"""Contract checks on the five entry scripts as shipped files.

The scripts run as plain files from the symlinked skill directory, so beyond the pure-logic
suites this verifies the file-level contract: a runnable `main(argv)`, a python3 shebang with the
executable bit, and the two source-level guards ported from the website suite (worktrees base on
`origin/main`; the Copilot re-review request uses the `[bot]`-suffixed login).
"""

import importlib
from pathlib import Path

import pytest
from view_issue import ISSUE_FIELDS

SCRIPTS_DIR = Path(__file__).parent.parent / "dot-claude" / "skills" / "resolve-issue" / "scripts"

EXECUTABLES = [
    "view_issue",
    "start_branch",
    "wait_for_copilot_review",
    "request_copilot_review",
    "finish_branch",
]


class TestIssueFields:
    def test_requests_an_explicit_field_list(self):
        fields = set(ISSUE_FIELDS.split(","))
        assert {"number", "title", "body", "state", "labels", "comments"} <= fields

    def test_never_asks_for_projectcards(self):
        # A bare `gh issue view` pulls in projectCards, which hard-errors on repos affected by the
        # Projects-classic deprecation.
        assert "projectCards" not in ISSUE_FIELDS


class TestExecutables:
    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_exposes_a_callable_main(self, module_name):
        module = importlib.import_module(module_name)
        assert callable(module.main)

    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_carries_a_python3_shebang(self, module_name):
        source = (SCRIPTS_DIR / f"{module_name}.py").read_text()
        assert source.startswith("#!/usr/bin/env python3\n")

    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_is_executable(self, module_name):
        assert (SCRIPTS_DIR / f"{module_name}.py").stat().st_mode & 0o111


class TestStartBranchWorktreeBase:
    def test_bases_the_worktree_on_origin_main(self):
        # A worktree must branch from the freshly fetched origin/main, not the never-updated local
        # `main` ref, to honor the "fresh main" promise without switching the current checkout.
        source = (SCRIPTS_DIR / "start_branch.py").read_text()
        assert '"origin/main"' in source
        assert '"worktree", "add", path, "-b", branch, "main"' not in source


class TestRequestCopilotReview:
    def test_requests_the_bot_suffixed_login_not_the_bare_one(self):
        source = (SCRIPTS_DIR / "request_copilot_review.py").read_text()
        assert "COPILOT_REVIEWER" in source
        assert 'reviewers[]=copilot-pull-request-reviewer"' not in source
