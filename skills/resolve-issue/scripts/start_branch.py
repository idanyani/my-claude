#!/usr/bin/env python3
"""Set up an isolated workspace for resolving an issue.

Usage: python3 <skill-dir>/scripts/start_branch.py <number> <kebab-summary> [--worktree]

Default: branch in place from a fresh `main`. With `--worktree`: create a sibling worktree instead.
Either way it refuses a dirty tree rather than stashing -- the caller surfaces that and asks the
user.
"""

import os
import sys

from lib.branch import branch_name, worktree_path, worktree_setup_hint
from lib.gh import run_git

USAGE = "usage: start_branch.py <number> <kebab-summary> [--worktree]"


def parse_args(argv: list[str]) -> tuple[int, str, bool]:
    worktree = "--worktree" in argv
    positional = [arg for arg in argv if arg != "--worktree"]
    if len(positional) < 2:
        raise ValueError(USAGE)
    try:
        issue_number = int(positional[0])
    except ValueError:
        raise ValueError(USAGE) from None
    summary = positional[1]
    if issue_number <= 0 or not summary:
        raise ValueError(USAGE)
    return issue_number, summary, worktree


def require_clean_tree() -> None:
    if run_git(["status", "--porcelain"]).strip():
        raise RuntimeError("working tree is dirty -- stop and ask the user; never stash silently.")


def main(argv: list[str]) -> int:
    issue_number, summary, worktree = parse_args(argv)
    branch = branch_name(issue_number, summary)

    require_clean_tree()
    # Prune so merged [gone] branches do not accumulate, then base the new branch on fresh main.
    run_git(["fetch", "--prune"])

    if worktree:
        repo_name = os.path.basename(run_git(["rev-parse", "--show-toplevel"]).strip())
        path = worktree_path(repo_name, issue_number)
        # Base on origin/main (fresh after the fetch above), not the local `main` ref, which the
        # worktree path never updates and so could be stale -- the "fresh main" promise holds
        # without disturbing the current checkout.
        run_git(["worktree", "add", path, "-b", branch, "origin/main"])
        hint = worktree_setup_hint(os.listdir(path))
        suffix = f" Run `{hint}` inside it." if hint else ""
        print(f"Worktree ready at {path} on branch {branch}.{suffix}")
        return 0

    run_git(["checkout", "main"])
    run_git(["pull"])
    run_git(["checkout", "-b", branch])
    print(f"Branch {branch} ready (in place).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
