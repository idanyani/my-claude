from pathlib import Path

import pytest
from git_repo import make_clone


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare `origin` whose `main` holds one commit; the test runs from inside it."""
    work = make_clone(tmp_path, "main")
    monkeypatch.chdir(work)
    return work
