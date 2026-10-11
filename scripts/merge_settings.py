#!/usr/bin/env python3
"""Merge the repo's settings.json into the live ~/.claude/settings.json.

Claude Code rewrites the live file at runtime, so it is merged rather than linked or copied:
every key the repo defines takes the repo's value, and keys that exist only on the machine are
kept. Objects merge recursively; any other value, lists included, is replaced whole, because a
list union would keep a permission the repo removed on every machine forever. Each kept key and
each overwritten differing value is reported on stderr, so drift is visible and can be folded
into the repo.

Usage: merge_settings.py <repo-settings.json> <live-settings.json>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from install_record import write_json_atomically

Settings = dict[str, Any]


def merge(repo: Settings, live: Settings) -> tuple[Settings, list[str], list[str]]:
    """Return the merged settings, the dotted paths kept from `live`, and those overwritten."""
    merged: Settings = {}
    kept: list[str] = []
    overwritten: list[str] = []
    _merge_into(merged, repo, live, "", kept, overwritten)
    return merged, kept, overwritten


def _merge_into(
    merged: Settings,
    repo: Settings,
    live: Settings,
    prefix: str,
    kept: list[str],
    overwritten: list[str],
) -> None:
    for key, live_value in live.items():
        path = prefix + key
        if key not in repo:
            merged[key] = live_value
            kept.append(path)
        elif isinstance(repo[key], dict) and isinstance(live_value, dict):
            merged[key] = {}
            _merge_into(merged[key], repo[key], live_value, path + ".", kept, overwritten)
        else:
            merged[key] = repo[key]
            if live_value != repo[key]:
                overwritten.append(path)
    for key, repo_value in repo.items():
        if key not in live:
            merged[key] = repo_value


def _read_live(path: Path) -> Settings:
    """Return the live settings, or none when the file is missing or not a JSON object."""
    if not path.exists():
        return {}
    try:
        live = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        live = None
    if not isinstance(live, dict):
        print(f"replacing {path}: not a JSON object", file=sys.stderr)
        return {}
    return live


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("live", type=Path)
    args = parser.parse_args(argv)

    repo = json.loads(args.repo.read_text(encoding="utf-8"))
    merged, kept, overwritten = merge(repo, _read_live(args.live))
    write_json_atomically(args.live, merged)

    for path in kept:
        print(
            f"kept machine-only setting {path} in {args.live}; "
            f"fold it into {args.repo} to keep it under version control",
            file=sys.stderr,
        )
    for path in overwritten:
        print(f"overwrote {path} in {args.live} with the value from {args.repo}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
