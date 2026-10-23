"""Tests for the `docs-review` skill's helper scripts.

Pure logic (scope filtering, link resolution) is unit-tested directly; the git-facing executable is
exercised against a throwaway repo built in a temp dir, mirroring how `resolve-issue`'s suites split
pure derivation from side effects.
"""

import importlib
from pathlib import Path

import pytest
from git_repo import commit, git, make_clone
from links import (
    extract_links,
    heading_slugs,
    is_intra_repo,
    link_is_broken,
    slugify,
)
from scope import filter_paths, is_ignored

SCRIPTS_DIR = Path(__file__).parent.parent / "dot-claude" / "skills" / "docs-review" / "scripts"
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


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """An empty git repo as the working directory."""
    git(tmp_path, "init", "-q", "-b", "main")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _branch_off_remote_default(work: Path) -> None:
    """Start `feature` from the remote default branch and change a tracked and a generated file."""
    git(work, "remote", "set-head", "origin", "--auto")
    git(work, "checkout", "-q", "-b", "feature", "origin/HEAD")
    (work / "kept.py").write_text("changed\n")
    (work / "uv.lock").write_text("noise\n")  # generated: must be filtered out


class TestChangedFilesAgainstClone:
    @pytest.fixture
    def feature(self, clone):
        """A branch off `origin/main` in a clone whose local `main` is one merge behind it."""
        (clone / "kept.py").write_text("base\n")
        (clone / "merged_elsewhere.py").write_text("other work\n")
        git(clone, "add", "-A")
        commit(clone, "another PR")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "reset", "-q", "--hard", "HEAD~1")
        _branch_off_remote_default(clone)
        return clone

    def test_reports_branch_changes_and_filters_generated(self, feature):
        import changed_files

        paths = filter_paths(changed_files.changed_paths())
        assert "kept.py" in paths
        assert "uv.lock" not in paths

    def test_ignores_work_merged_after_local_main_was_updated(self, feature):
        import changed_files

        assert "merged_elsewhere.py" not in changed_files.changed_paths()

    def test_records_a_missing_remote_default_branch(self, feature):
        import changed_files

        git(feature, "remote", "set-head", "origin", "--delete")

        assert "kept.py" in changed_files.changed_paths()

    def test_scopes_a_repo_without_a_main_branch(self, tmp_path, monkeypatch):
        import changed_files

        work = make_clone(tmp_path, "trunk")
        monkeypatch.chdir(work)
        _branch_off_remote_default(work)

        assert "kept.py" in changed_files.changed_paths()


class TestChangedFilesWithoutARemote:
    def test_scopes_against_local_main(self, temp_repo):
        import changed_files

        (temp_repo / "base.py").write_text("base\n")
        git(temp_repo, "add", "-A")
        commit(temp_repo, "base")
        git(temp_repo, "checkout", "-q", "-b", "feature")
        (temp_repo / "kept.py").write_text("new\n")
        git(temp_repo, "add", "-A")
        commit(temp_repo, "feature work")

        assert changed_files.changed_paths() == ["kept.py"]

    def test_reports_why_an_unreachable_remote_failed(self, temp_repo, tmp_path):
        import changed_files

        commit(temp_repo, "base")
        unreachable = tmp_path / "gone.git"
        git(temp_repo, "remote", "add", "origin", str(unreachable))

        with pytest.raises(RuntimeError, match=str(unreachable)):
            changed_files.changed_paths()


class TestCheckLinksAgainstTempRepo:
    @pytest.fixture
    def repo(self, temp_repo):
        (temp_repo / "good.md").write_text("[y](missing.md)\n")
        return temp_repo

    def _assert_skipped_and_good_reported(self, capsys, skipped: str) -> None:
        captured = capsys.readouterr()
        assert captured.out == "[HIGH] broken link 'missing.md' -- good.md:1\n"
        assert captured.err.startswith(f"skipped unreadable {skipped}: ")

    def test_reports_other_files_past_a_non_utf8_one(self, repo, capsys):
        import check_links

        (repo / "latin1.md").write_bytes("caf\xe9 [x](gone.md)\n".encode("latin-1"))

        assert check_links.main(["latin1.md", "good.md"]) == 0
        self._assert_skipped_and_good_reported(capsys, "latin1.md")

    def test_reports_other_files_past_one_gone_before_reading(self, repo, capsys, monkeypatch):
        import check_links

        # Simulates the file vanishing between the is_file() check and the read.
        monkeypatch.setattr(check_links.Path, "is_file", lambda self: True)

        assert check_links.main(["vanished.md", "good.md"]) == 0
        self._assert_skipped_and_good_reported(capsys, "vanished.md")
