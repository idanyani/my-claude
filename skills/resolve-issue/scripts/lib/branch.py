"""Pure helpers for `start_branch.py`.

Kept separate from the executable so unit tests import the derivation without running the
script's git side effects.
"""

import re
from collections.abc import Iterable


def branch_name(issue_number: int, summary: str) -> str:
    """Branch name for an issue: `<number>-<kebab-summary>`, e.g. `3-telegram-ingress`."""
    kebab = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
    if not kebab:
        raise ValueError("summary must contain at least one alphanumeric character")
    return f"{issue_number}-{kebab}"


def worktree_path(repo_name: str, issue_number: int) -> str:
    """Sibling worktree path for an issue, e.g. `../tiki-3`.

    The repo name is a parameter (the caller derives it from the checkout's top-level directory)
    so this one script serves every repo instead of hardcoding a project name.
    """
    return f"../{repo_name}-{issue_number}"


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
