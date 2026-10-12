#!/usr/bin/env python3
"""Set up the branch for resolving an issue.

Usage: python3 <skill-dir>/scripts/start_branch.py <number> <kebab-summary>

In a linked worktree -- one Claude Code created with EnterWorktree, subagent isolation, or
`claude --worktree` -- it switches the worktree to the issue's branch, based on a freshly fetched
`origin/main`, and drops the placeholder branch Claude Code named the worktree after. In the main
checkout it branches in place from a freshly pulled `main`. Either way it refuses a dirty tree
rather than stashing -- the caller surfaces that and asks the user -- and first deletes the local
branches whose PR merged (`lib/sweep.py`), so they do not accumulate.
"""

import os
import subprocess
import sys

from lib.branch import branch_name, worktree_setup_hint
from lib.gh import in_linked_worktree, run_git
from lib.sweep import DELETED, sweep_merged_branches

USAGE = "usage: start_branch.py <number> <kebab-summary>"
# Where Claude Code creates worktrees; untracked there, they would dirty the main checkout.
CLAUDE_WORKTREES_DIR = ".claude/worktrees/"


def parse_args(argv: list[str]) -> tuple[int, str]:
    if len(argv) != 2:
        raise ValueError(USAGE)
    try:
        issue_number = int(argv[0])
    except ValueError:
        raise ValueError(USAGE) from None
    summary = argv[1]
    if issue_number <= 0 or not summary:
        raise ValueError(USAGE)
    return issue_number, summary


def require_clean_tree() -> None:
    if run_git(["status", "--porcelain"]).strip():
        raise RuntimeError("working tree is dirty -- stop and ask the user; never stash silently.")


def report_sweep(outcomes: dict[str, str]) -> None:
    for branch, outcome in outcomes.items():
        if outcome == DELETED:
            print(f"Deleted merged branch {branch}.")
        else:
            print(f"Kept branch {branch}: {outcome}")


def is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", path], capture_output=True, text=True
    )
    # Exit 1 is a definite "not ignored"; any other nonzero status is a real failure.
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise RuntimeError(f"git check-ignore exited {result.returncode}: {result.stderr.strip()}")


def branch_linked_worktree(branch: str) -> None:
    placeholder = run_git(["branch", "--show-current"]).strip()
    # Base on origin/main (fresh after the sweep's fetch): the main checkout owns the local `main`,
    # which this worktree can neither check out nor pull. No upstream until the branch is pushed.
    run_git(["switch", "--no-track", "-c", branch, "origin/main"])
    if placeholder:
        try:
            # `-d`, not `-D`: git refuses when the placeholder holds commits not on the new branch.
            run_git(["branch", "-d", placeholder])
        except RuntimeError as error:
            print(f"Kept branch {placeholder}: {error}")
    if not is_ignored(CLAUDE_WORKTREES_DIR):
        print(
            f"Add `{CLAUDE_WORKTREES_DIR}` to the repo's .gitignore -- untracked, Claude Code's "
            "worktrees dirty the main checkout."
        )
    hint = worktree_setup_hint(os.listdir("."))
    suffix = f" Run `{hint}` in it." if hint else ""
    print(f"Branch {branch} ready in this worktree.{suffix}")


def main(argv: list[str]) -> int:
    issue_number, summary = parse_args(argv)
    branch = branch_name(issue_number, summary)

    require_clean_tree()
    linked = in_linked_worktree()
    if not linked:
        # Leave the current branch first, so the sweep may delete it if its PR merged.
        run_git(["checkout", "main"])
    # The sweep's fetch also freshens origin/main, the base of a worktree's branch.
    report_sweep(sweep_merged_branches())

    if linked:
        branch_linked_worktree(branch)
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
