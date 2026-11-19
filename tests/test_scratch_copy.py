"""Tests for dot-claude/bin/scratch-copy, run as a plain file against a real git repo."""

import subprocess
from pathlib import Path

import pytest
from git_repo import commit, git

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
    (repo / "un\ntracked").write_text("new")
    (repo / "ignored").write_text("cache")
    git(repo, "init", "-q", "nested")

    copy = scratch_copy(repo)

    assert files_in(copy) == {
        ".gitignore": "ignored\n",
        "edited": "uncommitted",
        "un\ntracked": "new",
    }


def make_repo_with_file(parent: Path, name: str, file: str) -> Path:
    git(parent, "init", "-q", name)
    (parent / name / file).write_text("committed")
    git(parent / name, "add", file)
    commit(parent / name, file)
    return parent / name


def add_submodule(repo: Path, source: Path, path: str) -> None:
    git(repo, "submodule", "add", "-q", str(source), path)
    commit(repo, path)


def test_copies_submodules_as_their_working_trees_stand(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
):
    # Git refuses submodules from a local path unless the file protocol is allowed.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")
    deep = make_repo_with_file(tmp_path, "deep-source", "deep_file")
    sub = make_repo_with_file(tmp_path, "sub-source", "edited")
    (sub / ".gitignore").write_text("ignored\n")
    git(sub, "add", ".gitignore")
    add_submodule(sub, deep, "deep")
    add_submodule(repo, sub, "sub")
    git(repo, "submodule", "update", "-q", "--init", "--recursive")
    (repo / "sub" / "edited").write_text("uncommitted")
    (repo / "sub" / "untracked").write_text("new")
    (repo / "sub" / "ignored").write_text("cache")

    copy = scratch_copy(repo)

    assert files_in(copy) == {
        ".gitmodules": (repo / ".gitmodules").read_text(),
        "sub/.gitignore": "ignored\n",
        "sub/.gitmodules": (repo / "sub" / ".gitmodules").read_text(),
        "sub/edited": "uncommitted",
        "sub/untracked": "new",
        "sub/deep/deep_file": "committed",
    }


def test_copies_the_whole_repo_from_a_subdirectory(repo: Path):
    (repo / "sub").mkdir()
    (repo / "sub" / "inner").write_text("in")
    (repo / "top").write_text("top")

    copy = scratch_copy(repo / "sub")

    assert files_in(copy) == {"sub/inner": "in", "top": "top"}


def test_fails_when_git_cannot_list_the_files(repo: Path):
    (repo / ".git" / "index").write_text("corrupt")

    result = subprocess.run([SCRIPT], cwd=repo, capture_output=True, text=True)

    assert result.returncode != 0


def test_fails_outside_a_repo_leaving_no_copy(tmp_path: Path, repo: Path):
    before = set(tmp_path.iterdir())

    result = subprocess.run([SCRIPT], cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode != 0
    assert set(tmp_path.iterdir()) == before
