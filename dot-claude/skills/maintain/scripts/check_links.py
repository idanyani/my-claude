#!/usr/bin/env python3
"""Report broken intra-repo markdown links, one finding per line.

Feeds the doc-freshness concern of a `maintain` sweep with the deterministic half of the work, so
the subagent spends its judgment on stale prose rather than path resolution. Takes markdown paths as
arguments (or on stdin, one per line); non-markdown paths are ignored.

Output: `[HIGH] broken link '<target>' -- <file>:<line>`. Always exits 0 -- this is a reporting aid,
not a gate.

Stdlib-only; needs `git` on PATH to locate the repo root.
"""

import subprocess
import sys
from pathlib import Path

from links import extract_links, is_intra_repo, link_is_broken


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(result.stdout.strip())


def broken_links_in(md_path: Path, repo_root: Path) -> list[tuple[int, str]]:
    """(line_number, target) for each broken intra-repo link in a markdown file."""
    text = md_path.read_text(encoding="utf-8")
    return [
        (line_number, target)
        for line_number, target in extract_links(text)
        if is_intra_repo(target) and link_is_broken(md_path, target, repo_root, text)
    ]


def _input_paths(argv: list[str]) -> list[str]:
    return argv if argv else [line for line in sys.stdin.read().splitlines() if line]


def main(argv: list[str]) -> int:
    repo_root = _repo_root()
    for raw in _input_paths(argv):
        path = Path(raw)
        if path.suffix != ".md" or not path.is_file():
            continue
        for line_number, target in broken_links_in(path, repo_root):
            print(f"[HIGH] broken link '{target}' -- {raw}:{line_number}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level CLI guard prints and exits non-zero
        print(error, file=sys.stderr)
        sys.exit(1)
