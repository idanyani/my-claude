"""Filter a file list down to what a maintenance audit should read.

Vendored, generated, and cache paths would drown the audit in noise and cost the subagents their
attention budget on files no human maintains. Pure so the executable can unit-test the exclusion
rules without a git checkout.
"""

from collections.abc import Iterable

# Path segments marking a directory as vendored, generated, or a tool cache -- never authored.
IGNORED_SEGMENTS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".tox",
        ".idea",
        ".next",
        "dist",
        "build",
        "target",
        "vendor",
        "coverage",
    }
)

# Suffixes for generated or binary artifacts whose contents no human maintains.
IGNORED_SUFFIXES = (".lock", ".min.js", ".min.css", ".map", ".pyc")

# Lockfiles whose name lacks a telling suffix (the `.lock` suffix already covers the rest).
IGNORED_BASENAMES = frozenset({"package-lock.json", "pnpm-lock.yaml"})


def is_ignored(path: str) -> bool:
    """Whether a repo-relative path is vendored, generated, or a tool cache."""
    parts = path.split("/")
    if any(segment in IGNORED_SEGMENTS for segment in parts):
        return True
    if parts[-1] in IGNORED_BASENAMES:
        return True
    return path.endswith(IGNORED_SUFFIXES)


def filter_paths(paths: Iterable[str]) -> list[str]:
    """The authored subset of `paths`, order preserved."""
    return [path for path in paths if not is_ignored(path)]
