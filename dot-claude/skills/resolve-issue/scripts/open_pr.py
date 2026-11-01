#!/usr/bin/env python3
"""Open the pull request for the current branch: push it to `origin`, then create the PR.

Usage: python3 <skill-dir>/scripts/open_pr.py

It refuses on `main`, on a detached HEAD, on a branch with no commits beyond `origin/main`, and
when none of those commits closes the issue the branch is named for. Otherwise it pushes the branch
with its upstream set, then creates the PR with the subject and body of the commit that closes the
issue as its title and description, and prints the PR's URL. Push review fixes afterwards with a
plain `git push`: once the branch is on the remote, its advertised tip already tells git what to
leave out.
"""

import sys

from lib.branch import closes_issue, issue_number
from lib.gh import current_branch, run_gh_text, run_git

USAGE = "usage: open_pr.py"


def push_branch(branch: str) -> None:
    # Without negotiation a push learns what the remote holds only from the tips it advertises
    # that the clone already has. Once another PR merges, `main`'s new tip is one the clone never
    # fetched, so the push would upload all history no held tip covers -- often all of it, for a
    # one-commit branch.
    run_git(["-c", "push.negotiate=true", "push", "-u", "origin", branch])


def refusal(branch: str, messages: list[str]) -> str | None:
    """Why the branch must not be pushed for a PR, or None when it may.

    `messages` holds one message per commit of the branch beyond `origin/main`. Nothing is pushed
    yet when this runs, so rewriting those commits is still safe.
    """
    if not branch:
        return "HEAD is detached -- check out the issue's branch and re-run."
    if branch == "main":
        return "on main -- run start_branch.py to branch for the issue, then re-run."
    if not messages:
        return f"{branch} has no commits beyond origin/main -- commit the work, then re-run."
    number = issue_number(branch)
    if number is None:
        return (
            f"{branch} is not named for an issue -- rename it with "
            "`git branch -m <number>-<summary>`, then re-run."
        )
    if not any(closes_issue(message, number) for message in messages):
        return (
            f"no commit on {branch} closes #{number} -- amend the last one's message to end with "
            f"`Resolves #{number}`, then re-run."
        )
    return None


def pr_text(messages: list[str], number: int) -> tuple[str, str]:
    """The PR's title and description: the subject and body of the commit that closes the issue.

    `messages` lists the newest commit first. Of several closing commits the oldest wins: it is the
    implementation, and a later one a follow-up.
    """
    closing = next(message for message in reversed(messages) if closes_issue(message, number))
    title, _, body = closing.partition("\n")
    return title, body.strip()


def main(argv: list[str]) -> int:
    if argv:
        raise ValueError(USAGE)
    branch = current_branch()
    # Checked before pushing: a branch pushed for a PR that cannot open lingers on the remote, and
    # start_branch.py's sweep keeps it because no merged PR holds it.
    log = run_git(["log", "-z", "--format=%B", "origin/main..HEAD"])
    messages = log.split("\0")[:-1] if log else []
    reason = refusal(branch, messages)
    if reason:
        raise RuntimeError(reason)
    push_branch(branch)
    number = issue_number(branch)
    assert number is not None  # refusal() rejects a branch not named for an issue
    title, body = pr_text(messages, number)
    print(run_gh_text(["pr", "create", "--title", title, "--body", body]).strip())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
