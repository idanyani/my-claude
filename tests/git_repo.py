"""Helpers for tests that run against real git repos (see the `clone` fixture in conftest.py)."""

import subprocess
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(cwd: Path, message: str) -> str:
    git(cwd, "commit", "--allow-empty", "-q", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def publish_pr_head(clone: Path, oid: str, pr: str) -> None:
    """Publish `oid` on `refs/pull/<pr>/head`, as GitHub does for every PR."""
    git(clone, "push", "-q", "origin", f"{oid}:refs/pull/{pr}/head")


def make_clone(tmp_path: Path, branch: str) -> Path:
    """Clone a bare `origin` whose `branch` holds one commit; `origin/HEAD` is left unrecorded."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", branch, str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-q", "-b", branch)
    commit(work, "base")
    git(work, "push", "-q", "-u", "origin", branch)
    return work
