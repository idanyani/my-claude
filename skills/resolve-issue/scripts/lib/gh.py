"""Subprocess shell-outs for the resolve-issue PR-lifecycle scripts.

One home for "run `gh`/`git`, surface a failure as a descriptive error." The pure decision logic
lives beside these in the other `lib/` modules and is unit-tested without touching the network;
these thin wrappers are the side-effecting seam the executables call.
"""

import json
import subprocess
from typing import Any


def _run(cmd: str, args: list[str]) -> str:
    """Run `<cmd> <args>` and return stdout, raising a descriptive error on a nonzero exit."""
    result = subprocess.run([cmd, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{cmd} {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def run_gh(args: list[str]) -> Any:
    """Run `gh <args>` and JSON-parse stdout (an untyped REST payload, hence Any)."""
    return json.loads(_run("gh", args))


def run_gh_text(args: list[str]) -> str:
    """Run `gh <args>` and return raw stdout, for callers that pass the output through verbatim."""
    return _run("gh", args)


def run_gh_paged(args: list[str]) -> list[Any]:
    """Run `gh <args>` across all pages and return one flat list.

    `--paginate --slurp` wraps each page in an outer array (`[[...], [...]]`); flatten it so callers
    filter a single list of records regardless of how many pages the endpoint spanned.
    """
    pages = run_gh([*args, "--paginate", "--slurp"])
    return [item for page in pages for item in page]


def run_git(args: list[str]) -> str:
    """Run `git <args>` and return stdout."""
    return _run("git", args)
