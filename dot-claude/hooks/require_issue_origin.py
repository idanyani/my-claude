#!/usr/bin/env python3
"""PreToolUse hook: refuse filing an issue except through file-issue's script.

Agents file issues under one account, whoever asked for the work, so only a label can tell work
the developer brought from work an agent proposed or started. file-issue's `file_issue.py` sets
that label, and falls back to no label only where one cannot be made. So a direct
`gh issue create` is refused, pointing to the script.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import sys
from typing import Any

from bash_commands import gh_issue_create_args, run_gate, simple_commands

HELP_FLAGS = frozenset({"--help", "-h"})


def refusal(payload: dict[str, Any]) -> str | None:
    """Why the command in `payload` is refused, or None to let it run."""
    for words in simple_commands(payload["tool_input"]["command"]):
        args = gh_issue_create_args(words)
        if args is not None and not HELP_FLAGS & set(args):
            return (
                "Refused: file issues with the file-issue skill's scripts/file_issue.py, which "
                "labels each issue with where its work came from. Load the skill (skill: "
                "file-issue) and follow its steps."
            )
    return None


def main(argv: list[str]) -> int:
    return run_gate(refusal, "Cannot check the command for a direct issue filing")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
