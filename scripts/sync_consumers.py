#!/usr/bin/env python3
"""Open a re-sync PR in every consuming repo whose generated Copilot instructions went stale.

Runs in the sync-consumers workflow under a GitHub App installation token (`GH_TOKEN`, with
`gh auth setup-git` already run so plain `git` authenticates through it). The consumer set is the
installation's repo selection -- adding a repo to the app installation opts it in, so no list is
kept here. Setup: docs/runbooks/copilot-sync-app.md.

Environment: `GH_TOKEN`, `APP_SLUG` (the app's slug, for the bot commit identity), and
`GITHUB_SHA` (the my-claude commit the conventions are rendered from).

Exit 0: every consumer is current or has a sync PR. Exit 1: at least one repo failed; the others
were still processed.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sync_copilot_instructions import (
    CANONICAL,
    INSTRUCTIONS_PATH,
    SOURCE_URL,
    Status,
    render_instructions,
    sync_repo,
)

# Owned by the bot and regenerated whole on every run, so force-pushing it never loses work.
SYNC_BRANCH = "sync-copilot-instructions"
PR_TITLE = "Regenerate Copilot instructions from the canonical conventions"


def consumer_repos(installation: dict[str, Any]) -> list[str]:
    """Full names of the repos the installation reaches; archived ones reject pushes."""
    return [repo["full_name"] for repo in installation["repositories"] if not repo["archived"]]


def arm_auto_merge(repo: dict[str, Any]) -> bool:
    """Whether the repo allows auto-merge; where it does not, the PR waits for a person."""
    return bool(repo.get("allow_auto_merge", False))


def bot_identity(app_slug: str, bot_user_id: int) -> tuple[str, str]:
    """Commit author (name, email) that GitHub attributes to the app's bot account."""
    name = f"{app_slug}[bot]"
    return name, f"{bot_user_id}+{name}@users.noreply.github.com"


def pr_body(source_sha: str) -> str:
    return (
        f"Regenerates `{INSTRUCTIONS_PATH}` from the canonical conventions at "
        f"{SOURCE_URL}/commit/{source_sha}, so this repo's Copilot reviews and its drift check "
        "follow the current rules.\n\n"
        "Opened by my-claude's sync-consumers workflow; the change it propagates, and why, is in "
        "the linked commit.\n"
    )


def run(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def installation_repos() -> dict[str, Any]:
    pages = json.loads(run(["gh", "api", "--paginate", "--slurp", "/installation/repositories"]))
    return {"repositories": [repo for page in pages for repo in page["repositories"]]}


def sync_consumer(full_name: str, expected: str, source_sha: str, author: tuple[str, str]) -> str:
    """Bring one consumer current and return a one-line report of what was done."""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp)
        run(["git", "clone", "--depth", "1", f"https://github.com/{full_name}.git", str(clone)])
        if sync_repo(clone, expected, write=True) is Status.CURRENT:
            return "current"

        name, email = author
        run(["git", "switch", "-c", SYNC_BRANCH], cwd=clone)
        run(["git", "add", str(INSTRUCTIONS_PATH)], cwd=clone)
        run(
            [
                "git",
                "-c",
                f"user.name={name}",
                "-c",
                f"user.email={email}",
                "commit",
                "-m",
                f"Regenerate Copilot instructions from my-claude@{source_sha[:7]}",
            ],
            cwd=clone,
        )
        run(["git", "push", "--force", "origin", SYNC_BRANCH], cwd=clone)

    existing = run(
        [
            "gh",
            "pr",
            "list",
            "-R",
            full_name,
            "--head",
            SYNC_BRANCH,
            "--state",
            "open",
            "--json",
            "url",
            "-q",
            ".[0].url",
        ]
    )
    if existing:
        run(["gh", "pr", "edit", existing, "--body", pr_body(source_sha)])
        url, verb = existing, "updated"
    else:
        url = run(
            [
                "gh",
                "pr",
                "create",
                "-R",
                full_name,
                "--head",
                SYNC_BRANCH,
                "--title",
                PR_TITLE,
                "--body",
                pr_body(source_sha),
            ]
        )
        verb = "opened"

    if arm_auto_merge(json.loads(run(["gh", "api", f"repos/{full_name}"]))):
        run(["gh", "pr", "merge", url, "--auto", "--squash", "--delete-branch"])
        return f"{verb} {url} (auto-merge armed)"
    return f"{verb} {url} (needs a manual merge)"


def main() -> int:
    source_sha = os.environ["GITHUB_SHA"]
    app_slug = os.environ["APP_SLUG"]
    bot_user_id = int(run(["gh", "api", f"/users/{app_slug}[bot]", "-q", ".id"]))
    author = bot_identity(app_slug, bot_user_id)
    expected = render_instructions(CANONICAL.read_text())

    failed = False
    for full_name in consumer_repos(installation_repos()):
        try:
            report = sync_consumer(full_name, expected, source_sha, author)
        except subprocess.CalledProcessError as error:
            failed = True
            report = f"FAILED: {' '.join(error.cmd[:3])}: {error.stderr.strip()}"
        print(f"{full_name}: {report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
