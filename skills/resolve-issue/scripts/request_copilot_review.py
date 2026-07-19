#!/usr/bin/env python3
"""Request one more Copilot review on a PR's final commit.

Copilot does not re-review later pushes on its own, so this is the way to get its take on
substantive fixes.
Usage: python3 <skill-dir>/scripts/request_copilot_review.py <pr>

Wraps the REST endpoint because `gh pr edit --add-reviewer` can hit a projectCards GraphQL
deprecation. Both the request and the review it later posts use the one `[bot]` login (see
lib/copilot_review.py).
"""

import sys

from lib.copilot_review import COPILOT_REVIEWER
from lib.gh import run_gh


def main(argv: list[str]) -> int:
    if not argv:
        raise ValueError("usage: request_copilot_review.py <pr>")
    pr = argv[0]
    run_gh(
        [
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{pr}/requested_reviewers",
            "-X",
            "POST",
            "-f",
            f"reviewers[]={COPILOT_REVIEWER}",
        ]
    )
    print(f"Requested a Copilot re-review on PR #{pr}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
