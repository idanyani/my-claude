#!/usr/bin/env python3
"""Wait for Copilot's advisory review on a PR, so it can be addressed before auto-merge is armed.

Usage: python3 <skill-dir>/scripts/wait_for_copilot_review.py <pr> [--timeout-seconds N]

Polls ONLY the review stream (REST `/pulls/{pr}/reviews`), never `gh pr checks`: the review and CI
checks are independent event streams, and auto-merge already handles `verify`, so gating the wait on
a check would block on the wrong, slower signal (see references/git-workflow.md).

Exit 0: a genuine review posted -- its state, body, and inline findings are printed to act on.
Exit 2: the bounded wait expired without a review -- run an in-session `/code-review <pr>` instead.
Exit 3: Copilot posted an "unable to review" notice (e.g. over quota) -- run
`/code-review <pr>` instead.
Neither 2 nor 3 gates the merge; both signal that no usable Copilot review was obtained.
"""

import sys
import time
from typing import Any

from lib.copilot_review import find_copilot_review, format_review_comments, poll_decision
from lib.gh import run_gh_paged

DEFAULT_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 20


def parse_args(argv: list[str]) -> tuple[str, int]:
    flag_index = argv.index("--timeout-seconds") if "--timeout-seconds" in argv else -1
    # Only drop the flag and its value when the flag is actually present; otherwise flag_index is
    # -1 and `flag_index + 1` is 0, which would silently swallow the <pr> positional.
    positional = [
        arg
        for i, arg in enumerate(argv)
        if flag_index == -1 or (i != flag_index and i != flag_index + 1)
    ]
    if not positional:
        raise ValueError("usage: wait_for_copilot_review.py <pr> [--timeout-seconds N]")
    pr = positional[0]

    if flag_index == -1:
        seconds: float = DEFAULT_TIMEOUT_SECONDS
    else:
        raw = argv[flag_index + 1] if flag_index + 1 < len(argv) else None
        try:
            seconds = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            seconds = 0
        if seconds <= 0:
            raise ValueError(f'--timeout-seconds must be a positive number, got "{raw}"')
    return pr, int(seconds * 1000)


def latest_reviews(pr: str) -> list[dict[str, Any]]:
    return run_gh_paged(["api", f"repos/{{owner}}/{{repo}}/pulls/{pr}/reviews"])


def inline_findings(pr: str, review_id: int) -> str:
    comments = run_gh_paged(
        ["api", f"repos/{{owner}}/{{repo}}/pulls/{pr}/reviews/{review_id}/comments"]
    )
    return format_review_comments(comments)


def main(argv: list[str]) -> int:
    pr, timeout_ms = parse_args(argv)
    start = time.monotonic()

    while True:
        reviews = latest_reviews(pr)
        elapsed_ms = (time.monotonic() - start) * 1000
        outcome = poll_decision(reviews, elapsed_ms, timeout_ms)

        if outcome == "found":
            review = find_copilot_review(reviews)
            assert review is not None  # poll_decision returned "found"
            print(f"Copilot review ({review['state']}):\n{review['body']}")
            print(f"\n{inline_findings(pr, review['id'])}")
            return 0
        if outcome == "unavailable":
            review = find_copilot_review(reviews)
            assert review is not None  # poll_decision returned "unavailable"
            print(f"Copilot review ({review['state']}):\n{review['body']}")
            print(
                f"Copilot was unable to review -- run an in-session /code-review {pr} instead.",
                file=sys.stderr,
            )
            return 3
        if outcome == "timeout":
            print(
                f"No Copilot review after {timeout_ms / 1000:g}s -- "
                f"run an in-session /code-review {pr} instead.",
                file=sys.stderr,
            )
            return 2
        # Cap the sleep to the time left so a full interval cannot overshoot --timeout-seconds.
        time.sleep(min(POLL_INTERVAL_SECONDS, (timeout_ms - elapsed_ms) / 1000))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
