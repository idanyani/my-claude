"""Subprocess shell-outs for the resolve-issue PR-lifecycle scripts.

One home for "run `gh`/`git`, surface a failure as a descriptive error." These thin wrappers are
the side-effecting seam the executables and `sweep.py` call; the pure decision logic beside them
in `lib/` is unit-tested without touching the network.
"""

import json
import subprocess
from typing import Any


def _run(cmd: str, args: list[str]) -> str:
    """Run `<cmd> <args>` and return stdout, raising a descriptive error on a nonzero exit."""
    result = subprocess.run([cmd, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{cmd} {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def run_gh(args: list[str]) -> Any:
    """Run `gh <args>` and JSON-parse stdout (an untyped REST payload, hence Any)."""
    return json.loads(_run("gh", args))


def run_gh_text(args: list[str]) -> str:
    """Run `gh <args>` and return raw stdout, for callers that pass the output through verbatim."""
    return _run("gh", args)


def arm_auto_merge(pr: str) -> str:
    """Arm a squash auto-merge, or merge at once if gh reads the PR as ready; returns gh's report."""
    return run_gh_text(["pr", "merge", pr, "--auto", "--squash", "--delete-branch"]).strip()


def run_git(args: list[str]) -> str:
    """Run `git <args>` and return stdout."""
    return _run("git", args)


def in_linked_worktree() -> bool:
    """Whether the current directory is in a linked worktree rather than the main checkout."""
    git_dir, common_dir = run_git(
        ["rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"]
    ).splitlines()
    return git_dir != common_dir


def git_succeeds(args: list[str]) -> bool:
    """Run a yes/no `git <args>` (exit 0 = yes, 1 = no), raising on any other exit status.

    Exit 1 is a definite "no"; any other nonzero status is a real failure that must surface
    rather than masquerade as a "no".
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise RuntimeError(f"git {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}")
