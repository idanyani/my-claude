#!/usr/bin/env python3
"""Merge the repo's settings.json into the live ~/.claude/settings.json.

Claude Code rewrites the live file at runtime, so it is merged rather than linked or copied:
every key the repo defines takes the repo's value, and keys that exist only on the machine are
kept. Objects merge recursively; any other value, lists included, is replaced whole, because a
list union would keep a permission the repo removed on every machine forever.

A key absent from the repo is either the machine's own or one the repo dropped. To tell them
apart, the paths the repo ships are kept in the install record (install_record.py) under the
"settings" kind, as JSON Pointers (RFC 6901) so a key containing a dot stays unambiguous; a
recorded path the repo no longer ships is removed from the live file, keeping any machine-only
key nested inside it. With no "settings" kind in the record, every path the repo's file shipped
in its git history stands in for it, so keys dropped before the record existed are retired too.

Each kept key, removed key, and overwritten differing value is reported on stderr, so drift is
visible and can be folded into the repo; an overwrite report carries the live value it replaced.
When the merge overwrites or removes anything, the live file is first copied next to itself with
a BACKUP_SUFFIX, so every discarded value stays recoverable as restorable JSON after the run's
output is gone. The backup holds the last run that discarded something; earlier backups are
replaced rather than accumulated.

Usage: merge_settings.py <repo-settings.json> <live-settings.json> <record-file>
"""

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Any, NamedTuple

from install_record import read_record, retired, write_json_atomically, write_kind

Settings = dict[str, Any]
KeyPath = tuple[str, ...]

SETTINGS_KIND = "settings"
BACKUP_SUFFIX = ".bak"


class Merge(NamedTuple):
    """The merged settings, the dotted paths kept from live and removed, and the live value of
    each dotted path the repo overwrote."""

    merged: Settings
    kept: list[str]
    overwritten: dict[str, Any]
    removed: list[str]


def shipped_paths(settings: Settings) -> set[str]:
    """Return the JSON Pointer of every key in `settings`, nested object keys included."""
    return {_pointer(keys) for keys in _key_paths(settings, ())}


def merge(repo: Settings, live: Settings, dropped: Collection[str] = ()) -> Merge:
    """Merge `repo` into `live`, removing the live keys whose JSON Pointer is in `dropped`."""
    return _merge(repo, live, (), set(dropped))


def _merge(repo: Settings, live: Settings, prefix: KeyPath, dropped: set[str]) -> Merge:
    result = Merge({}, [], {}, [])
    for key, live_value in live.items():
        keys = (*prefix, key)
        if key in repo:
            if isinstance(repo[key], dict) and isinstance(live_value, dict):
                _absorb(result, key, _merge(repo[key], live_value, keys, dropped))
            else:
                result.merged[key] = repo[key]
                if live_value != repo[key]:
                    result.overwritten[_dotted(keys)] = live_value
        elif _pointer(keys) not in dropped:
            result.merged[key] = live_value
            result.kept.append(_dotted(keys))
        elif isinstance(live_value, dict):
            # The machine may have added its own keys inside an object the repo dropped; those
            # stay, and the object goes as one removal only when nothing of the machine's is left.
            inner = _merge({}, live_value, keys, dropped)
            if inner.merged:
                _absorb(result, key, inner)
            else:
                result.removed.append(_dotted(keys))
        else:
            result.removed.append(_dotted(keys))
    for key, repo_value in repo.items():
        if key not in live:
            result.merged[key] = repo_value
    return result


def _absorb(result: Merge, key: str, inner: Merge) -> None:
    result.merged[key] = inner.merged
    result.kept.extend(inner.kept)
    result.overwritten.update(inner.overwritten)
    result.removed.extend(inner.removed)


def _key_paths(settings: Settings, prefix: KeyPath) -> Iterator[KeyPath]:
    for key, value in settings.items():
        keys = (*prefix, key)
        yield keys
        if isinstance(value, dict):
            yield from _key_paths(value, keys)


def _pointer(keys: KeyPath) -> str:
    return "".join("/" + key.replace("~", "~0").replace("/", "~1") for key in keys)


def _dotted(keys: KeyPath) -> str:
    return ".".join(keys)


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


def _committed_versions(repo: Path) -> Iterator[Settings]:
    """Yield each committed version of `repo` that is a JSON object; none outside a git clone."""
    git = ["git", "-C", str(repo.parent)]
    try:
        log = subprocess.run(
            [*git, "log", "--format=%H", "--", repo.name], capture_output=True, text=True
        )
    except FileNotFoundError:  # no git installed
        return
    if log.returncode != 0:
        return
    for commit in log.stdout.split():
        show = subprocess.run(
            [*git, "show", f"{commit}:./{repo.name}"], capture_output=True, text=True
        )
        try:
            version = json.loads(show.stdout)
        except json.JSONDecodeError:
            continue
        if isinstance(version, dict):
            yield version


def _recorded_paths(record: Path, repo: Path) -> set[str]:
    kinds = read_record(record)
    if SETTINGS_KIND in kinds:
        return set(kinds[SETTINGS_KIND])
    return set().union(*(shipped_paths(version) for version in _committed_versions(repo)))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("live", type=Path)
    parser.add_argument("record", type=Path)
    args = parser.parse_args(argv)

    repo = json.loads(args.repo.read_text(encoding="utf-8"))
    shipped = shipped_paths(repo)
    dropped = retired(_recorded_paths(args.record, args.repo), shipped)
    result = merge(repo, _read_live(args.live), dropped)
    if result.overwritten or result.removed:
        backup = args.live.with_name(args.live.name + BACKUP_SUFFIX)
        shutil.copyfile(args.live, backup)
        print(f"backed up {args.live} to {backup} before merging", file=sys.stderr)
    write_json_atomically(args.live, result.merged)
    write_kind(args.record, SETTINGS_KIND, shipped)

    for path in result.kept:
        print(
            f"kept machine-only setting {path} in {args.live}; "
            f"fold it into {args.repo} to keep it under version control",
            file=sys.stderr,
        )
    for path in result.removed:
        print(f"removed {path} from {args.live}: {args.repo} no longer ships it", file=sys.stderr)
    for path, live_value in result.overwritten.items():
        print(
            f"overwrote {path} in {args.live} with the value from {args.repo}; "
            f"it held {json.dumps(live_value)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
