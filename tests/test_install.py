"""Tests for install.sh as a whole: a change to an installed clone reinstalls it."""

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from git_repo import commit, git, make_clone

REPO = Path(__file__).parent.parent
HOOK = "dot-claude/hooks/x.py"
SETTINGS = "dot-claude/settings.json"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # install.sh, and the git hooks that rerun it, install into the HOME they inherit.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A clone, pushed to its bare origin, shipping install.sh and one registered hook."""
    work = make_clone(tmp_path, "main")
    shutil.copy2(REPO / "install.sh", work)
    shutil.copytree(
        REPO / "scripts", work / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    (work / HOOK).parent.mkdir(parents=True)
    (work / HOOK).write_text("")
    hook = {"type": "command", "command": 'python3 "$HOME/.claude/hooks/x.py"'}
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [hook]}]}}
    (work / SETTINGS).write_text(json.dumps(settings))
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "ship install.sh and a hook")
    git(work, "push", "-q")
    return work


@pytest.fixture
def installed(tmp_path: Path, upstream: Path, home: Path) -> Path:
    """A second clone of the origin, installed into `home`."""
    clone = tmp_path / "installed"
    git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(clone))
    subprocess.run([clone / "install.sh"], check=True, capture_output=True)
    return clone


def live_settings(home: Path) -> dict[str, object]:
    return json.loads((home / ".claude" / "settings.json").read_text())


def merge_pull(clone: Path) -> None:
    git(clone, "pull", "-q")


def rebase_pull(clone: Path) -> None:
    # With no local commit to replay, a rebase pull is a plain fast-forward.
    commit(clone, "local")
    git(clone, "pull", "-q", "--rebase")


def checkout(clone: Path) -> None:
    git(clone, "fetch", "-q")
    git(clone, "checkout", "-q", "-b", "latest", "origin/main")


@pytest.mark.parametrize("update", [merge_pull, rebase_pull, checkout])
def test_an_update_that_drops_a_hook_unregisters_it(
    upstream: Path, installed: Path, home: Path, update: Callable[[Path], None]
):
    assert "hooks" in live_settings(home)
    git(upstream, "rm", "-q", HOOK)
    (upstream / SETTINGS).write_text("{}")
    git(upstream, "commit", "-q", "-am", "drop the hook")
    git(upstream, "push", "-q")
    update(installed)
    assert "hooks" not in live_settings(home)
    assert not (home / ".claude" / "hooks" / "x.py").is_symlink()


def test_a_pull_in_a_worktree_keeps_the_install_linked_to_the_main_clone(
    tmp_path: Path, upstream: Path, installed: Path, home: Path
):
    worktree = tmp_path / "worktree"
    git(installed, "worktree", "add", "-q", "-b", "side", str(worktree), "origin/main")
    commit(upstream, "more")
    git(upstream, "push", "-q")
    git(worktree, "pull", "-q")
    link = home / ".claude" / "hooks" / "x.py"
    assert link.resolve() == (installed / HOOK).resolve()
