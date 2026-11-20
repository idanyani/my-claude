#!/usr/bin/env python3
"""PreToolUse hook: refuse filing an issue that does not record where its work came from.

Agents file issues under one account, whoever asked for the work, so the author cannot tell work
the developer brought from work an agent proposed or started. Each issue therefore carries
exactly one origin label, and `gh issue create` is refused, with the labels to choose from, when
it sets none, an unknown one, or more than one. The file-issue skill says which label fits.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import sys
from itertools import pairwise
from typing import Any

from bash_commands import gh_issue_create_args, run_gate, simple_commands

ORIGIN_LABELS = ("origin:developer", "origin:proposed", "origin:agent")
ORIGIN_PREFIX = "origin:"
LABEL_FLAGS = ("--label", "-l")
HELP_FLAGS = frozenset({"--help", "-h"})


def labels_of(args: list[str]) -> list[str]:
    """The labels a `gh issue create` command's arguments set."""
    values = [value for flag, value in pairwise(args) if flag in LABEL_FLAGS]
    values += [arg.removeprefix("--label=") for arg in args if arg.startswith("--label=")]
    values += [arg.removeprefix("-l") for arg in args if arg.startswith("-l") and arg != "-l"]
    return [label.strip() for value in values for label in value.split(",") if label.strip()]


def refusal(payload: dict[str, Any]) -> str | None:
    """Why the command in `payload` is refused, or None to let it run."""
    for words in simple_commands(payload["tool_input"]["command"]):
        args = gh_issue_create_args(words)
        if args is None or HELP_FLAGS & set(args):
            continue
        origins = {label for label in labels_of(args) if label.startswith(ORIGIN_PREFIX)}
        if len(origins) != 1 or not origins <= set(ORIGIN_LABELS):
            return (
                "Refused: an issue must carry exactly one origin label, set with --label: "
                f"{', '.join(ORIGIN_LABELS)}. The file-issue skill says which one fits."
            )
    return None


def main(argv: list[str]) -> int:
    return run_gate(refusal, "Cannot check the command for an issue's origin label")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
