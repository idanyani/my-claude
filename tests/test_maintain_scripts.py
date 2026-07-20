"""Tests for the `maintain` skill's helper scripts.

Pure logic (scope filtering, link resolution) is unit-tested directly; the git-facing executable is
exercised against a throwaway repo built in a temp dir, mirroring how `resolve-issue`'s suites split
pure derivation from side effects.
"""

import importlib
import subprocess
from pathlib import Path

import pytest
from links import (
    extract_links,
    heading_slugs,
    is_intra_repo,
    link_is_broken,
    slugify,
)
from scope import filter_paths, is_ignored

SCRIPTS_DIR = Path(__file__).parent.parent / "dot-claude" / "skills" / "maintain" / "scripts"
EXECUTABLES = ["changed_files", "check_links"]


class TestScope:
    def test_keeps_authored_source_and_docs(self):
        paths = ["src/app.py", "docs/guide.md", "README.md"]
        assert filter_paths(paths) == paths

    @pytest.mark.parametrize(
        "path",
        [
            ".venv/lib/x.py",
            "node_modules/pkg/index.js",
            "src/__pycache__/app.cpython-312.pyc",
            "uv.lock",
            "package-lock.json",
            "web/app.min.js",
        ],
    )
    def test_drops_vendored_generated_and_cache_paths(self, path):
        assert is_ignored(path)

    def test_preserves_order(self):
        assert filter_paths(["b.py", ".venv/x", "a.py"]) == ["b.py", "a.py"]


class TestLinkParsing:
    def test_extracts_inline_links_with_line_numbers(self):
        markdown = "intro\nsee [the guide](docs/guide.md) here"
        assert extract_links(markdown) == [(2, "docs/guide.md")]

    def test_ignores_external_and_protocol_relative_targets(self):
        assert not is_intra_repo("https://example.com")
        assert not is_intra_repo("mailto:x@y.z")
        assert not is_intra_repo("//cdn.example.com/a.js")

    def test_treats_relative_paths_as_intra_repo(self):
        assert is_intra_repo("../other/file.md")
        assert is_intra_repo("#a-heading")


class TestSlugs:
    def test_slugify_matches_github_style(self):
        assert slugify("Phase 2 -- Read the Issue!") == "phase-2----read-the-issue"

    def test_heading_slugs_collects_atx_headings(self):
        assert heading_slugs("# Title\n\n## Sub Section\ntext") == {"title", "sub-section"}


class TestLinkResolution:
    def test_missing_file_is_broken(self, tmp_path):
        source = tmp_path / "a.md"
        assert link_is_broken(source, "does-not-exist.md", tmp_path, "text")

    def test_existing_file_is_not_broken(self, tmp_path):
        (tmp_path / "target.md").write_text("hi")
        source = tmp_path / "a.md"
        assert not link_is_broken(source, "target.md", tmp_path, "text")

    def test_root_relative_resolves_from_repo_root(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "t.md").write_text("hi")
        source = tmp_path / "nested" / "a.md"
        assert not link_is_broken(source, "/docs/t.md", tmp_path, "text")

    def test_same_file_anchor_checks_headings(self, tmp_path):
        source = tmp_path / "a.md"
        body = "# Overview\n\n## Setup Steps\n"
        assert not link_is_broken(source, "#setup-steps", tmp_path, body)
        assert link_is_broken(source, "#missing", tmp_path, body)

    def test_external_link_is_never_broken(self, tmp_path):
        assert not link_is_broken(tmp_path / "a.md", "https://example.com", tmp_path, "text")


class TestExecutables:
    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_exposes_a_callable_main(self, module_name):
        assert callable(importlib.import_module(module_name).main)

    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_carries_a_python3_shebang(self, module_name):
        assert (
            (SCRIPTS_DIR / f"{module_name}.py").read_text().startswith("#!/usr/bin/env python3\n")
        )

    @pytest.mark.parametrize("module_name", EXECUTABLES)
    def test_is_executable(self, module_name):
        assert (SCRIPTS_DIR / f"{module_name}.py").stat().st_mode & 0o111


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


class TestChangedFilesAgainstTempRepo:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        _git(tmp_path, "init", "-b", "main")
        _git(tmp_path, "config", "user.email", "t@e.st")
        _git(tmp_path, "config", "user.name", "Tester")
        (tmp_path / "kept.py").write_text("base\n")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-m", "base")
        _git(tmp_path, "checkout", "-b", "feature")
        (tmp_path / "kept.py").write_text("changed\n")
        (tmp_path / "uv.lock").write_text("noise\n")  # generated: must be filtered out
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_reports_branch_changes_and_filters_generated(self, repo):
        import changed_files

        paths = filter_paths(changed_files.changed_paths())
        assert "kept.py" in paths
        assert "uv.lock" not in paths
