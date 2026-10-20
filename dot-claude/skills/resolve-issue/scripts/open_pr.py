#!/usr/bin/env python3
"""Open the pull request for the current branch: push it to `origin`, then create the PR.

Usage: python3 <skill-dir>/scripts/open_pr.py

It pushes the branch with its upstream set, then runs `gh pr create --fill`, which turns the
commit body into the PR description, and prints the PR's URL. Push review fixes afterwards with a
plain `git push`: once the branch is on the remote, its advertised tip already tells git what to
leave out.
"""

import sys

from lib.gh import run_gh_text, run_git

USAGE = "usage: open_pr.py"


def push_branch(branch: str) -> None:
    # Without negotiation a push learns what the remote holds only from the tips it advertises
    # that the clone already has. Once another PR merges, `main`'s new tip is one the clone never
    # fetched, so the push would upload all history no held tip covers -- often all of it, for a
    # one-commit branch (idanyani/my-claude#99).
    run_git(["-c", "push.negotiate=true", "push", "-u", "origin", branch])


def main(argv: list[str]) -> int:
    if argv:
        raise ValueError(USAGE)
    push_branch(run_git(["branch", "--show-current"]).strip())
    print(run_gh_text(["pr", "create", "--fill"]).strip())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
