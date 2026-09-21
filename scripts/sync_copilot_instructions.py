#!/usr/bin/env python3
"""Propagate the canonical conventions into each consuming repo's Copilot instructions file.

GitHub Copilot code review reads `.github/copilot-instructions.md` from the repo under review.
Organization-level instructions would avoid the per-repo copy, but they need paid Copilot Business
seats and GitHub exposes no API for them -- nothing can read the setting back, so a stale mirror is
undetectable. A generated file in each repo costs one copy and buys the opposite property: it lives
in git, so drift is a diff and a CI check rather than an act of faith.

Exit status reports drift rather than failure, as code generators and `git diff --exit-code` do: 1
means at least one repo was out of date, whether or not `--write` then fixed it. That makes the
same command usable as a CI gate and as the local refresh.

Stdlib-only, like the skill scripts, so a consuming repo can run it without installing anything.
"""

import enum
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = REPO_ROOT / "dot-claude" / "CLAUDE.md"

# Relative to a consuming repo's root; the path Copilot code review reads.
INSTRUCTIONS_PATH = Path(".github") / "copilot-instructions.md"

SOURCE_URL = "https://github.com/idanyani/my-claude"

BANNER = f"""<!--
Generated file -- do not edit here.

Canonical source: dot-claude/CLAUDE.md in {SOURCE_URL}
Edit the conventions there and re-run scripts/sync_copilot_instructions.py; an edit made directly
to this file is overwritten by the next sync.
-->
"""


class Status(enum.Enum):
    """How a consuming repo's instructions file compares to the rendered canonical text."""

    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"


def render_instructions(conventions: str) -> str:
    """The full instructions-file text for `conventions`, banner included."""
    return f"{BANNER}\n{conventions}"


def status_for(existing: str | None, expected: str) -> Status:
    """Compare a repo's current file contents (None when absent) against the expected text."""
    if existing is None:
        return Status.MISSING
    return Status.CURRENT if existing == expected else Status.STALE


def sync_repo(repo: Path, expected: str, write: bool) -> Status:
    """Status of `repo`'s instructions file, writing `expected` into place when `write` is set.

    The returned status always describes what was found *before* any write, so a caller can report
    what changed.
    """
    target = repo / INSTRUCTIONS_PATH
    existing = target.read_text() if target.exists() else None
    status = status_for(existing, expected)
    if write and status is not Status.CURRENT:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected)
    return status


def main(argv: list[str]) -> int:
    """Verify (default) or rewrite (`--write`) the instructions file in each repo path in `argv`."""
    write = "--write" in argv
    repos = [Path(arg) for arg in argv if not arg.startswith("--")]
    if not repos:
        print(f"usage: {Path(__file__).name} <repo-path>... [--write]", file=sys.stderr)
        return 2

    expected = render_instructions(CANONICAL.read_text())
    drifted = False
    for repo in repos:
        status = sync_repo(repo, expected, write)
        drifted = drifted or status is not Status.CURRENT
        print(f"{status.value:<8} {repo}")
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
