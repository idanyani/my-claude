#!/usr/bin/env python3
"""Print a GitHub issue as JSON for the resolve-issue workflow.

Usage: python3 <skill-dir>/scripts/view_issue.py <number>

Pins an explicit field list. A bare `gh issue view` pulls in `projectCards`, which hard-errors on
repos affected by the Projects-classic deprecation.
"""

import sys

from lib.gh import run_gh_text

ISSUE_FIELDS = "number,title,body,state,labels,comments"


def main(argv: list[str]) -> int:
    if not argv:
        raise ValueError("usage: view_issue.py <number>")
    issue_number = argv[0]
    print(run_gh_text(["issue", "view", issue_number, "--json", ISSUE_FIELDS]), end="")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
