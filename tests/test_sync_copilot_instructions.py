"""Tests for the Copilot instructions sync script.

Rendering and comparison are pure and unit-tested directly; the filesystem-facing helpers run
against throwaway repo directories in a temp dir, mirroring how the skill suites split pure
derivation from side effects.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from sync_copilot_instructions import (
    CANONICAL,
    INSTRUCTIONS_PATH,
    SOURCE_URL,
    Status,
    main,
    render_instructions,
    status_for,
    sync_repo,
)

SCRIPT = Path(__file__).parent.parent / "scripts" / "sync_copilot_instructions.py"

CONVENTIONS = "# Working conventions\n\n## Git commit messages\n\n- Imperative verb.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty consuming-repo directory."""
    (tmp_path / ".github").mkdir()
    return tmp_path


class TestRender:
    def test_carries_the_conventions_verbatim(self):
        assert CONVENTIONS in render_instructions(CONVENTIONS)

    def test_names_the_canonical_source_so_editors_know_where_to_go(self):
        rendered = render_instructions(CONVENTIONS)
        assert SOURCE_URL in rendered
        assert "dot-claude/CLAUDE.md" in rendered

    def test_warns_against_editing_the_generated_copy(self):
        assert "do not edit" in render_instructions(CONVENTIONS).lower()

    def test_banner_precedes_the_conventions(self):
        rendered = render_instructions(CONVENTIONS)
        assert rendered.index(SOURCE_URL) < rendered.index("## Git commit messages")

    def test_is_ascii_per_the_prose_conventions(self):
        render_instructions(CONVENTIONS).encode("ascii")

    def test_is_deterministic(self):
        assert render_instructions(CONVENTIONS) == render_instructions(CONVENTIONS)


class TestStatus:
    def test_absent_file_is_missing(self):
        assert status_for(None, "expected") is Status.MISSING

    def test_identical_file_is_current(self):
        assert status_for("expected", "expected") is Status.CURRENT

    def test_differing_file_is_stale(self):
        assert status_for("old text", "expected") is Status.STALE

    def test_empty_file_is_stale_not_missing(self):
        assert status_for("", "expected") is Status.STALE


class TestSyncRepo:
    def test_reports_missing_without_writing_when_not_asked(self, repo: Path):
        assert sync_repo(repo, "expected", write=False) is Status.MISSING
        assert not (repo / INSTRUCTIONS_PATH).exists()

    def test_writes_the_expected_text_when_asked(self, repo: Path):
        assert sync_repo(repo, "expected", write=True) is Status.MISSING
        assert (repo / INSTRUCTIONS_PATH).read_text() == "expected"

    def test_reports_the_status_found_before_the_write(self, repo: Path):
        (repo / INSTRUCTIONS_PATH).write_text("old text")
        assert sync_repo(repo, "expected", write=True) is Status.STALE
        assert (repo / INSTRUCTIONS_PATH).read_text() == "expected"

    def test_leaves_a_current_file_alone(self, repo: Path):
        (repo / INSTRUCTIONS_PATH).write_text("expected")
        assert sync_repo(repo, "expected", write=True) is Status.CURRENT

    def test_creates_the_github_directory_when_absent(self, tmp_path: Path):
        assert sync_repo(tmp_path, "expected", write=True) is Status.MISSING
        assert (tmp_path / INSTRUCTIONS_PATH).read_text() == "expected"


class TestMain:
    def test_verify_fails_on_a_repo_missing_the_file(self, repo: Path):
        assert main([str(repo)]) == 1

    def test_verify_passes_once_written(self, repo: Path):
        assert main([str(repo), "--write"]) == 1
        assert main([str(repo)]) == 0

    def test_write_is_idempotent(self, repo: Path):
        main([str(repo), "--write"])
        assert main([str(repo), "--write"]) == 0

    def test_reports_every_repo_not_just_the_first(self, tmp_path: Path, capsys):
        first, second = tmp_path / "first", tmp_path / "second"
        first.mkdir()
        second.mkdir()
        assert main([str(first), str(second)]) == 1
        output = capsys.readouterr().out
        assert "first" in output and "second" in output

    def test_writes_the_real_conventions(self, repo: Path):
        main([str(repo), "--write"])
        assert CANONICAL.read_text() in (repo / INSTRUCTIONS_PATH).read_text()


class TestExecutable:
    def test_runs_as_a_plain_file(self, repo: Path):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(repo), "--write"], capture_output=True, text=True
        )
        assert result.returncode == 1, result.stderr
        assert (repo / INSTRUCTIONS_PATH).exists()
