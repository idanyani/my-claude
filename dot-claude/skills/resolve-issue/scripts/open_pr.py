#!/usr/bin/env python3
"""Open the pull request for the current branch: push it to `origin`, then create the PR.

Usage: python3 <skill-dir>/scripts/open_pr.py

It refuses on `main`, on a detached HEAD, and on a branch with no commits beyond `origin/main`.
Otherwise it pushes the branch with its upstream set, then runs `gh pr create --fill`, which turns the
commit body into the PR description, and prints the PR's URL. Push review fixes afterwards with a
plain `git push`: once the branch is on the remote, its advertised tip already tells git what to
leave out.
"""

import sys

from lib.gh import current_branch, run_gh_text, run_git

USAGE = "usage: open_pr.py"


def push_branch(branch: str) -> None:
    # Without negotiation a push learns what the remote holds only from the tips it advertises
    # that the clone already has. Once another PR merges, `main`'s new tip is one the clone never
    # fetched, so the push would upload all history no held tip covers -- often all of it, for a
    # one-commit branch (idanyani/my-claude#99).
    run_git(["-c", "push.negotiate=true", "push", "-u", "origin", branch])


def refusal(branch: str, commits_ahead: int) -> str | None:
    """Why the branch must not be pushed for a PR, or None when it may."""
    if not branch:
        return "HEAD is detached -- check out the issue's branch and re-run."
    if branch == "main":
        return "on main -- run start_branch.py to branch for the issue, then re-run."
    if not commits_ahead:
        return f"{branch} has no commits beyond origin/main -- commit the work, then re-run."
    return None


def main(argv: list[str]) -> int:
    if argv:
        raise ValueError(USAGE)
    branch = current_branch()
    # Checked before pushing: a branch pushed for a PR that cannot open lingers on the remote, and
    # start_branch.py's sweep keeps it because no merged PR holds it.
    commits_ahead = int(run_git(["rev-list", "--count", "origin/main..HEAD"]))
    reason = refusal(branch, commits_ahead)
    if reason:
        raise RuntimeError(reason)
    push_branch(branch)
    print(run_gh_text(["pr", "create", "--fill"]).strip())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
