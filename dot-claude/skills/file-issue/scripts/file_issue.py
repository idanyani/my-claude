#!/usr/bin/env python3
"""File a GitHub issue labeled with where its work came from.

Usage: python3 <skill-dir>/scripts/file_issue.py --origin developer|proposed|agent
           --title <title> --body-file <file> [--repo <owner/name>]

Agents file every issue under one account, so the label is the only record of whether the
developer brought the work, approved an agent's proposal, or an agent started it. The script
creates the label first, with a fixed color. A repo the session cannot write to, such as an
upstream project, refuses to create it; there the issue is filed without a label, and the script
says so. Anywhere else a failure stops the filing, so an issue in the developer's own repos never
lands without its origin. Prints the new issue's URL.

Stdlib-only: it needs just `python3` and `gh` on PATH.
"""

import argparse
import subprocess
import sys
from collections.abc import Callable

Gh = Callable[[list[str]], subprocess.CompletedProcess[str]]

ORIGINS = ("developer", "proposed", "agent")
LABEL_COLOR = "c5def5"
# GitHub's repository roles that may create labels.
LABEL_CREATING_PERMISSIONS = frozenset({"ADMIN", "MAINTAIN", "WRITE"})


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def _failure(args: list[str], result: subprocess.CompletedProcess[str]) -> RuntimeError:
    return RuntimeError(f"gh {' '.join(args)} exited {result.returncode}: {result.stderr.strip()}")


def file_issue(origin: str, title: str, body_file: str, repo: str | None, gh: Gh) -> str:
    """File the issue and return its URL; label it `origin:<origin>` wherever a label can be made."""
    repo_args = ["--repo", repo] if repo else []
    label = f"origin:{origin}"
    label_args = ["--label", label]
    make_label = ["label", "create", label, "--force", "--color", LABEL_COLOR, *repo_args]
    made = gh(make_label)
    if made.returncode != 0:
        permission = gh(
            [
                "repo",
                "view",
                *([repo] if repo else []),
                "--json",
                "viewerPermission",
                "-q",
                ".viewerPermission",
            ]
        )
        if permission.returncode != 0 or permission.stdout.strip() in LABEL_CREATING_PERMISSIONS:
            raise _failure(make_label, made)
        label_args = []
    create = [
        "issue",
        "create",
        "--title",
        title,
        "--body-file",
        body_file,
        *repo_args,
        *label_args,
    ]
    created = gh(create)
    if created.returncode != 0:
        raise _failure(create, created)
    if not label_args:
        print(f"Filed without {label}: this session cannot create labels there.", file=sys.stderr)
    return created.stdout.strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="file_issue.py")
    parser.add_argument("--origin", required=True, choices=ORIGINS)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    print(file_issue(args.origin, args.title, args.body_file, args.repo, run_gh))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
