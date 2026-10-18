from pathlib import Path

import pytest
from git_repo import commit, git


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare `origin` whose `main` holds one commit; the test runs from inside it."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-q", "-b", "main")
    commit(work, "base")
    git(work, "push", "-q", "-u", "origin", "main")
    monkeypatch.chdir(work)
    return work
