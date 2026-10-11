#!/usr/bin/env python3
"""Set up an isolated workspace for resolving an issue.

Usage: python3 <skill-dir>/scripts/start_branch.py <number> <kebab-summary> [--worktree]

Default: branch in place from a fresh `main`. With `--worktree`: create a sibling worktree instead.
Either way it refuses a dirty tree rather than stashing -- the caller surfaces that and asks the
user -- and first deletes the local branches whose PR merged (`lib/sweep.py`), so they do not
accumulate.
"""

import os
import sys

from lib.branch import branch_name, worktree_path, worktree_setup_hint
from lib.gh import run_git
from lib.sweep import DELETED, parse_main_worktree, sweep_merged_branches

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


def report_sweep(outcomes: dict[str, str]) -> None:
    for branch, outcome in outcomes.items():
        if outcome == DELETED:
            print(f"Deleted merged branch {branch}.")
        else:
            print(f"Kept branch {branch}: {outcome}")


def main(argv: list[str]) -> int:
    issue_number, summary, worktree = parse_args(argv)
    branch = branch_name(issue_number, summary)

    require_clean_tree()
    if not worktree:
        # Leave the current branch first, so the sweep may delete it if its PR merged.
        run_git(["checkout", "main"])
    # The sweep's fetch also freshens origin/main, the base of the new branch.
    report_sweep(sweep_merged_branches())

    if worktree:
        # Name and place the worktree after the main checkout, even when run from a sibling.
        main_checkout = parse_main_worktree(run_git(["worktree", "list", "--porcelain"]))
        path = os.path.normpath(
            os.path.join(
                main_checkout, worktree_path(os.path.basename(main_checkout), issue_number)
            )
        )
        # Base on origin/main (fresh after the sweep's fetch), not the local `main` ref, which the
        # worktree path never updates and so could be stale -- the "fresh main" promise holds
        # without disturbing the current checkout.
        run_git(["worktree", "add", path, "-b", branch, "origin/main"])
        hint = worktree_setup_hint(os.listdir(path))
        suffix = f" Run `{hint}` inside it." if hint else ""
        print(f"Worktree ready at {path} on branch {branch}.{suffix}")
        return 0

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
