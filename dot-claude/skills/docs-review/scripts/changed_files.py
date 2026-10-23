#!/usr/bin/env python3
"""Print the file set a `docs-review` should read, one path per line.

Default scope is the current branch's work: files changed since the merge-base with the remote
default branch (`origin/HEAD`), plus uncommitted and untracked changes. `--all` widens to every
tracked file. Vendored, generated, and cache paths are filtered out (see scope.py) so the review
reads only authored files.

The base is the remote-tracking ref, not a local `main`: a local `main` may lag the remote, so the
diff would claim work merged since as the branch's own, and the default branch may have another
name. A clone may lack `origin/HEAD`, so a missing one is first recorded with `git remote set-head`.

Stdlib-only; needs `git` on PATH and runs against the current working directory's repo.
"""

import subprocess
import sys

from scope import filter_paths

REMOTE_DEFAULT_BRANCH = "origin/HEAD"


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


def _ensure_remote_default_branch() -> None:
    probe = ["git", "rev-parse", "--verify", "--quiet", REMOTE_DEFAULT_BRANCH]
    if subprocess.run(probe, capture_output=True).returncode != 0:
        _git_lines(["remote", "set-head", "origin", "--auto"])


def changed_paths() -> list[str]:
    """Authored files touched on this branch: committed since merge-base, staged, and untracked."""
    _ensure_remote_default_branch()
    paths = set()
    paths.update(_git_lines(["diff", "--name-only", "--merge-base", REMOTE_DEFAULT_BRANCH]))
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
