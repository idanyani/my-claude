#!/usr/bin/env python3
"""Merge the repo's settings.json into the live ~/.claude/settings.json.

Claude Code rewrites the live file at runtime, so it is merged rather than linked or copied:
every key the repo defines takes the repo's value, and keys that exist only on the machine are
kept. Objects merge recursively; a list is the repo's elements followed by the live elements the
repo does not own, so an entry another tool or the machine added (a hook, a permission) survives;
any other value is replaced whole.

A key or list element absent from the repo is either the machine's own or one the repo dropped.
To tell them apart, the install record (install_record.py) keeps what the repo ships: its key
paths under the "settings" kind, and its list elements under the "settings-elements" kind, each
as a JSON Pointer (RFC 6901) so a key containing a dot stays unambiguous; a list element's last
segment is its canonical JSON. A recorded path the repo no longer ships is removed from the live
file, keeping any machine-only key or list element nested inside it, and a recorded list element
the repo no longer ships is removed from its list. For a kind missing from the record, everything
the repo's file shipped in its git history stands in for it, so what the repo dropped before the
record existed is retired too.

Each kept key or list element, removed key, and overwritten differing value is reported on
stderr, so drift is visible and can be folded into the repo; an overwrite report carries the live
value it replaced. When the merge overwrites or removes anything, or replaces a live file that is
not a JSON object, the live file is first copied next to itself with a BACKUP_SUFFIX, so every
discarded value stays recoverable as restorable JSON after the run's output is gone. The backup holds the last run that discarded something; earlier backups are
replaced rather than accumulated.

Usage: merge_settings.py <repo-settings.json> <live-settings.json> <record-file>
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Collection, Iterator
from pathlib import Path
from typing import Any, NamedTuple

from install_record import (
    read_record,
    retired,
    write_atomically,
    write_json_atomically,
    write_kind,
)

Settings = dict[str, Any]
KeyPath = tuple[str, ...]

SETTINGS_KIND = "settings"
ELEMENTS_KIND = "settings-elements"
BACKUP_SUFFIX = ".bak"


class Merge(NamedTuple):
    """The merged settings, the dotted paths (and list elements) kept from live and removed, and
    the live value of each dotted path the repo overwrote."""

    merged: Settings
    kept: list[str]
    overwritten: dict[str, Any]
    removed: list[str]


def shipped_paths(settings: Settings) -> set[str]:
    """Return the JSON Pointer of every key in `settings`, nested object keys included."""
    return {_pointer(keys) for keys, _ in _key_values(settings, ())}


def shipped_elements(settings: Settings) -> set[str]:
    """Return the JSON Pointer of every list element in `settings`, nested lists included."""
    return {
        _element_pointer(keys, element)
        for keys, value in _key_values(settings, ())
        if isinstance(value, list)
        for element in value
    }


def merge(
    repo: Settings, live: Settings, dropped: Collection[str] = (), owned: Collection[str] = ()
) -> Merge:
    """Merge `repo` into `live`, removing the live keys whose JSON Pointer is in `dropped` and the
    live list elements whose JSON Pointer is in `owned` or `repo` ships."""
    return _merge(repo, live, (), set(dropped), set(owned) | shipped_elements(repo))


def _merge(
    repo: Settings, live: Settings, prefix: KeyPath, dropped: set[str], owned: set[str]
) -> Merge:
    result = Merge({}, [], {}, [])
    for key, live_value in live.items():
        keys = (*prefix, key)
        if key in repo:
            if isinstance(repo[key], dict) and isinstance(live_value, dict):
                _absorb(result, key, _merge(repo[key], live_value, keys, dropped, owned))
                continue
            value = repo[key]
            if isinstance(value, list) and isinstance(live_value, list):
                value = value + _keep_foreign(result, keys, live_value, owned)
            result.merged[key] = value
            if live_value != value:
                result.overwritten[_dotted(keys)] = live_value
        elif _pointer(keys) not in dropped:
            result.merged[key] = live_value
            result.kept.append(_dotted(keys))
        elif isinstance(live_value, dict):
            # The machine may have added its own keys inside an object the repo dropped; those
            # stay, and the object goes as one removal only when nothing of the machine's is left.
            inner = _merge({}, live_value, keys, dropped, owned)
            if inner.merged:
                _absorb(result, key, inner)
            else:
                result.removed.append(_dotted(keys))
        elif isinstance(live_value, list) and (
            foreign := _keep_foreign(result, keys, live_value, owned)
        ):
            result.merged[key] = foreign
            if live_value != foreign:
                result.overwritten[_dotted(keys)] = live_value
        else:
            result.removed.append(_dotted(keys))
    for key, repo_value in repo.items():
        if key not in live:
            result.merged[key] = repo_value
    return result


def _keep_foreign(result: Merge, keys: KeyPath, live: list[Any], owned: set[str]) -> list[Any]:
    """Return the elements of the `live` list at `keys` not in `owned`, reporting each as kept."""
    foreign = [element for element in live if _element_pointer(keys, element) not in owned]
    result.kept.extend(f"{_dotted(keys)} {json.dumps(element)}" for element in foreign)
    return foreign


def _absorb(result: Merge, key: str, inner: Merge) -> None:
    result.merged[key] = inner.merged
    result.kept.extend(inner.kept)
    result.overwritten.update(inner.overwritten)
    result.removed.extend(inner.removed)


def _key_values(settings: Settings, prefix: KeyPath) -> Iterator[tuple[KeyPath, Any]]:
    for key, value in settings.items():
        keys = (*prefix, key)
        yield keys, value
        if isinstance(value, dict):
            yield from _key_values(value, keys)


def _pointer(keys: KeyPath) -> str:
    return "".join("/" + key.replace("~", "~0").replace("/", "~1") for key in keys)


def _element_pointer(keys: KeyPath, element: Any) -> str:
    return _pointer((*keys, json.dumps(element, sort_keys=True)))


def _dotted(keys: KeyPath) -> str:
    return ".".join(keys)


def _parse_live(path: Path, content: bytes) -> Settings | None:
    """Return the live settings in `content`, or None when they are not a JSON object."""
    try:
        live = json.loads(content)
    except ValueError:  # malformed JSON or text that is not UTF-8
        live = None
    if not isinstance(live, dict):
        print(f"replacing {path}: not a JSON object", file=sys.stderr)
        return None
    return live


def _back_up(live: Path, content: bytes) -> None:
    """Write `content` next to the file `live` resolves to, with that file's mode."""
    target = live.resolve()
    backup = target.with_name(target.name + BACKUP_SUFFIX)
    write_atomically(backup, content, mode=target.stat().st_mode & 0o777)
    print(f"backed up {live} to {backup} before merging", file=sys.stderr)


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


def _recorded(
    record: Path, repo: Path, shipped: dict[str, Callable[[Settings], set[str]]]
) -> dict[str, set[str]]:
    """Return the recorded entries of each kind in `shipped`, standing in for a kind missing from
    the record with what that kind's function finds in every committed version of `repo`."""
    kinds = read_record(record)
    missing = [kind for kind in shipped if kind not in kinds]
    versions = list(_committed_versions(repo)) if missing else []
    return {
        kind: set(kinds[kind]) if kind in kinds else set().union(*map(extract, versions))
        for kind, extract in shipped.items()
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("live", type=Path)
    parser.add_argument("record", type=Path)
    args = parser.parse_args(argv)

    repo = json.loads(args.repo.read_text(encoding="utf-8"))
    paths, elements = shipped_paths(repo), shipped_elements(repo)
    recorded = _recorded(
        args.record, args.repo, {SETTINGS_KIND: shipped_paths, ELEMENTS_KIND: shipped_elements}
    )
    dropped = retired(recorded[SETTINGS_KIND], paths)
    original = args.live.read_bytes() if args.live.exists() else None
    live = {} if original is None else _parse_live(args.live, original)
    result = merge(repo, live or {}, dropped, recorded[ELEMENTS_KIND])
    if original is not None and (live is None or result.overwritten or result.removed):
        _back_up(args.live, original)
    write_json_atomically(args.live, result.merged)
    write_kind(args.record, SETTINGS_KIND, paths)
    write_kind(args.record, ELEMENTS_KIND, elements)

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
