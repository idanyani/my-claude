"""Tests for dot-claude/bin/scratch-copy, run as a plain file against a real git repo."""

import subprocess
from pathlib import Path

import pytest
from git_repo import git

SCRIPT = Path(__file__).parent.parent / "dot-claude" / "bin" / "scratch-copy"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Keeps each copy under the test's own temporary directory, which pytest cleans up.
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    git(tmp_path, "init", "-q", "repo")
    return tmp_path / "repo"


def scratch_copy(cwd: Path) -> Path:
    """Run the script from `cwd` and return the copy it prints, checking it prints nothing else."""
    result = subprocess.run([SCRIPT], cwd=cwd, check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    return Path(lines[0])


def files_in(directory: Path) -> dict[str, str]:
    """Map every file under `directory`, `.git` included, to its content."""
    return {
        str(path.relative_to(directory)): path.read_text()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_copies_the_working_tree_as_git_lists_it_without_git_data(repo: Path):
    (repo / ".gitignore").write_text("ignored\n")
    (repo / "edited").write_text("committed")
    (repo / "deleted").write_text("committed")
    git(repo, "add", ".gitignore", "edited", "deleted")
    git(repo, "commit", "-q", "-m", "files")
    (repo / "edited").write_text("uncommitted")
    (repo / "deleted").unlink()
    (repo / "untracked").write_text("new")
    (repo / "ignored").write_text("cache")

    copy = scratch_copy(repo)

    assert files_in(copy) == {
        ".gitignore": "ignored\n",
        "edited": "uncommitted",
        "untracked": "new",
    }


def test_copies_the_whole_repo_from_a_subdirectory(repo: Path):
    (repo / "sub").mkdir()
    (repo / "sub" / "inner").write_text("in")
    (repo / "top").write_text("top")

    copy = scratch_copy(repo / "sub")

    assert files_in(copy) == {"sub/inner": "in", "top": "top"}
