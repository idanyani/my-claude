#!/usr/bin/env python3
"""Print the file set a `maintain` sweep should audit, one path per line.

Default scope is the current branch's work: files changed since the merge-base with `main`, plus
uncommitted and untracked changes -- this matches the pain the skill targets (debris left *during*
a development cycle). `--all` widens to every tracked file. Vendored, generated, and cache paths are
filtered out (see scope.py) so the audit reads only authored files.

Stdlib-only; needs `git` on PATH and runs against the current working directory's repo.
"""

import subprocess
import sys

from scope import filter_paths


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


def changed_paths(base: str = "main") -> list[str]:
    """Authored files touched on this branch: committed since merge-base, staged, and untracked."""
    paths = set()
    paths.update(_git_lines(["diff", "--name-only", "--merge-base", base]))
    paths.update(_git_lines(["diff", "--name-only", "HEAD"]))
    paths.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))
    return sorted(paths)


def all_tracked_paths() -> list[str]:
    """Every tracked file in the repo."""
    return sorted(_git_lines(["ls-files"]))


def main(argv: list[str]) -> int:
    paths = all_tracked_paths() if argv[:1] == ["--all"] else changed_paths()
    for path in filter_paths(paths):
        print(path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
