#!/usr/bin/env python3
"""Set up the branch for resolving an issue.

Usage: python3 <skill-dir>/scripts/start_branch.py <number> <kebab-summary>

In a linked worktree -- one Claude Code created with EnterWorktree, subagent isolation, or
`claude --worktree` -- it switches the worktree to the issue's branch, based on a freshly fetched
`origin/main`, and drops the placeholder branch Claude Code named the worktree after. In the main
checkout it branches in place from a freshly pulled `main`. Either way it refuses a dirty tree
rather than stashing -- the caller surfaces that and asks the user -- and first deletes the local
and remote branches whose PR merged (`lib/sweep.py`), so they do not accumulate, and re-arms the
user's PRs whose armed auto-merge GitHub never fired (`lib/stall.py`).
"""

import os
import sys

from lib.branch import branch_name, worktree_setup_hint
from lib.gh import current_branch, git_succeeds, in_linked_worktree, run_git
from lib.stall import MERGED, REARMED, rearm_stalled_prs
from lib.sweep import DELETED, sweep_merged_branches

USAGE = "usage: start_branch.py <number> <kebab-summary>"
# Where Claude Code creates worktrees; untracked there, they would dirty the main checkout.
CLAUDE_WORKTREES_DIR = ".claude/worktrees/"
# Claude Code names a new worktree's branch `worktree-<name>`; only such a branch is ours to drop.
CLAUDE_PLACEHOLDER_PREFIX = "worktree-"


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


def report_stalled_prs() -> None:
    # A stall check that cannot reach GitHub must not keep the next issue from starting.
    try:
        outcomes = rearm_stalled_prs()
    except RuntimeError as error:
        print(f"Could not check for stalled PRs: {error}")
        return
    for pr, outcome in outcomes.items():
        if outcome == REARMED:
            print(f"Re-armed auto-merge on PR #{pr}: it was ready but GitHub had not merged it.")
        elif outcome == MERGED:
            print(f"PR #{pr} merged after it sat ready with auto-merge armed.")
        else:
            print(f"PR #{pr} is ready but GitHub has not merged it: {outcome}")


def ignore_claude_worktrees(toplevel: str) -> None:
    """Keep Claude Code's worktrees out of every checkout's status, repo `.gitignore` or not.

    `info/exclude` is local to the clone and shared by all its worktrees, so this needs no commit
    in the consuming repo.
    """
    if git_succeeds(["check-ignore", "--quiet", os.path.join(toplevel, CLAUDE_WORKTREES_DIR)]):
        return
    exclude = run_git(["rev-parse", "--path-format=absolute", "--git-path", "info/exclude"])
    os.makedirs(os.path.dirname(exclude.strip()), exist_ok=True)
    with open(exclude.strip(), "a") as exclude_file:
        exclude_file.write(f"{CLAUDE_WORKTREES_DIR}\n")


def branch_linked_worktree(branch: str, toplevel: str) -> None:
    placeholder = current_branch()
    # Base on origin/main (fresh after the sweep's fetch): the main checkout owns the local `main`,
    # which this worktree can neither check out nor pull. No upstream until the branch is pushed.
    run_git(["switch", "--no-track", "-c", branch, "origin/main"])
    if placeholder.startswith(CLAUDE_PLACEHOLDER_PREFIX):
        try:
            # `-d`, not `-D`: git refuses when the placeholder holds commits not on the new branch.
            run_git(["branch", "-d", placeholder])
        except RuntimeError as error:
            print(f"Kept branch {placeholder}: {error}")
    hint = worktree_setup_hint(os.listdir(toplevel))
    suffix = f" Run `{hint}` in it." if hint else ""
    print(f"Branch {branch} ready in this worktree.{suffix}")


def main(argv: list[str]) -> int:
    issue_number, summary = parse_args(argv)
    branch = branch_name(issue_number, summary)

    toplevel = run_git(["rev-parse", "--show-toplevel"]).strip()
    ignore_claude_worktrees(toplevel)
    require_clean_tree()
    linked = in_linked_worktree()
    if not linked:
        # Leave the current branch first, so the sweep may delete it if its PR merged.
        run_git(["checkout", "main"])
    # The sweep's fetch also freshens origin/main, the base of a worktree's branch.
    report_sweep(sweep_merged_branches())
    report_stalled_prs()

    if linked:
        branch_linked_worktree(branch, toplevel)
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
