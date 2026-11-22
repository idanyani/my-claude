#!/usr/bin/env python3
"""PreToolUse hook: refuse filing an issue, or opening or merging a PR, except through skill scripts.

Each of these commands carries a step that a skill's script adds. file-issue's `file_issue.py`
labels the issue with where its work came from: agents file issues under one account, whoever
asked for the work, so only the label tells them apart. resolve-issue's `open_pr.py` opens the PR
into `main` from the commit that resolves its issue, and `finish_branch.py` arms its auto-merge
only once the skill's review steps are done. So the direct `gh` command is refused, naming the
script. Disarming a PR's auto-merge (`gh pr merge --disable-auto`) merges nothing and runs.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import sys
from typing import Any

from bash_commands import SKILL_SCRIPTS, gh_command, run_gate, simple_commands

HELP_FLAGS = frozenset({"--help", "-h"})

# Each gated `gh` subcommand: the script that carries it out, what the script adds, and the flags
# that let the direct command run because it then changes nothing.
GATED: dict[tuple[str, ...], tuple[str, str, frozenset[str]]] = {
    ("issue", "create"): (
        "file_issue.py",
        "labels each issue with where its work came from",
        HELP_FLAGS,
    ),
    ("pr", "create"): (
        "open_pr.py",
        "opens the PR into main from the commit that resolves its issue",
        HELP_FLAGS,
    ),
    ("pr", "merge"): (
        "finish_branch.py",
        "arms auto-merge once the skill's review steps are done",
        HELP_FLAGS | {"--disable-auto"},
    ),
}


def refusal(payload: dict[str, Any]) -> str | None:
    """Why the command in `payload` is refused, or None to let it run."""
    for words in simple_commands(payload["tool_input"]["command"]):
        found = gh_command(words)
        if found is None:
            continue
        subcommand, args = found
        gated = GATED.get(subcommand)
        if gated is None:
            continue
        script, adds, harmless_flags = gated
        if harmless_flags & set(args):
            continue
        skill = SKILL_SCRIPTS[script]
        return (
            f"Refused: run `gh {' '.join(subcommand)}` through the {skill} skill's "
            f"scripts/{script}, which {adds}. Load the skill (skill: {skill}) and follow its steps."
        )
    return None


def main(argv: list[str]) -> int:
    return run_gate(refusal, "Cannot check the command for an issue filing or a PR command")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
