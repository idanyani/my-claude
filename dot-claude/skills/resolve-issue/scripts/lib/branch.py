"""Pure helpers for `start_branch.py` and `open_pr.py`.

Kept separate from the executables so unit tests import the derivation without running the
scripts' git side effects.
"""

import re
from collections.abc import Iterable


def branch_name(issue_number: int, summary: str) -> str:
    """Branch name for an issue: `<number>-<kebab-summary>`, e.g. `3-telegram-ingress`."""
    kebab = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
    if not kebab:
        raise ValueError("summary must contain at least one alphanumeric character")
    return f"{issue_number}-{kebab}"


def issue_number(branch: str) -> int | None:
    """The issue a branch named by `branch_name` resolves, or None for any other branch."""
    match = re.match(r"(\d+)-.", branch)
    return int(match.group(1)) if match else None


# GitHub's closing keywords, optionally followed by a colon, then the issue on the same line,
# optionally qualified by `owner/repo` -- a cross-repo close names its repo deliberately:
# https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
CLOSING_KEYWORD = (
    r"(?<![\w-])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?[ \t]+(?:[\w.-]+/[\w.-]+)?#"
)


def closes_issue(messages: str, number: int) -> bool:
    """Whether commit messages close issue `number` once they reach the default branch."""
    return re.search(rf"{CLOSING_KEYWORD}{number}(?!\d)", messages, re.IGNORECASE) is not None


# Dependency-install hints keyed by the project file that calls for them, in preference order:
# a repo with both a pyproject.toml and a package.json is Python-first here.
WORKTREE_SETUP_HINTS = (
    ("pyproject.toml", "uv sync"),
    ("package.json", "pnpm install"),
)


def worktree_setup_hint(filenames: Iterable[str]) -> str | None:
    """The dependency-install command a fresh worktree needs, from its top-level files, or None."""
    present = set(filenames)
    for project_file, hint in WORKTREE_SETUP_HINTS:
        if project_file in present:
            return hint
    return None
