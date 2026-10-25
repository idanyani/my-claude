#!/usr/bin/env python3
"""Merge the repo's settings.json into the live ~/.claude/settings.json.

Claude Code rewrites the live file at runtime, so it is merged rather than linked or copied:
every key the repo defines takes the repo's value, and keys that exist only on the machine are
kept. Objects merge recursively; a list keeps its live order and the live elements the repo does
not own, so an entry another tool or the machine added (a hook, a permission) survives; any other
value is replaced whole. An object in a list is identified by every field but its MEMBER_FIELDS
(a hook group by its matcher), whose lists merge like a top-level list, so a hook another tool
added inside one of the repo's groups stays in that group.

A key or list element absent from the repo is either the machine's own or one the repo dropped.
To tell them apart, the install record (install_record.py) keeps what the repo ships: its key
paths under SETTINGS_KIND, and its list elements under ELEMENTS_KIND, each as a JSON Pointer
(RFC 6901) so a key containing a dot stays unambiguous; a list element's segment is its identity
as canonical JSON. A recorded path the repo no longer ships is removed from the live file,
keeping any machine-only key or list element nested inside it, and a recorded list element the
repo no longer ships is removed from its list. For a kind missing from the record, everything
the repo's file shipped in its git history stands in for it, so what the repo dropped before the
record existed is retired too.

Each removed key and overwritten differing value is reported on stderr, so drift is visible and
can be folded into the repo; an overwrite report carries the live value it replaced. A kept key or
list element is reported only on the run that first keeps it: the record holds what the last run
kept under KEPT_KIND, because some machine-only settings belong to another tool and can never be
folded in, and repeating them on every run would bury the reports that need action.

When the merge overwrites or removes anything, or replaces a live file that is not a JSON object,
the live file is first copied next to itself with a BACKUP_SUFFIX, so every discarded value stays
recoverable as restorable JSON after the run's output is gone. The backup holds the last run that
discarded something; earlier backups are replaced rather than accumulated.

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
    Record,
    read_record,
    retired,
    write_atomically,
    write_json_atomically,
    write_kinds,
)

Settings = dict[str, Any]
KeyPath = tuple[str, ...]

SETTINGS_KIND = "settings"
# Named for how it identifies an element: a record naming elements by another identity must be
# missing this kind, so that git history stands in for it rather than entries nothing matches.
ELEMENTS_KIND = "settings-element-identities"
KEPT_KIND = "settings-kept"
BACKUP_SUFFIX = ".bak"
# The list fields of an object in a list whose elements merge one by one, like a top-level list:
# a hook group's handlers, which other tools add to. Any other list field (a handler's args) is an
# ordered value and part of the object's identity.
MEMBER_FIELDS = frozenset({"hooks"})


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
    """Return the JSON Pointer of every list element in `settings`, including the elements of
    lists nested in objects and in the MEMBER_FIELDS of an object in a list."""
    return {
        pointer
        for keys, value in _key_values(settings, ())
        if isinstance(value, list)
        for pointer in _list_pointers(keys, value)
    }


def _list_pointers(keys: KeyPath, elements: list[Any]) -> Iterator[str]:
    for element in elements:
        identity = _identity(element)
        yield _pointer((*keys, identity))
        for field, members in _members(element).items():
            yield from _list_pointers((*keys, identity, field), members)


def merge(
    repo: Settings, live: Settings, dropped: Collection[str] = (), owned: Collection[str] = ()
) -> Merge:
    """Merge `repo` into `live`, removing the live keys whose JSON Pointer is in `dropped` and the
    live list elements whose JSON Pointer is in `owned` and that `repo` no longer ships."""
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
                value = _merge_list(result, keys, value, live_value, owned)
            result.merged[key] = value
            if _discards(live_value, value):
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
            foreign := _merge_list(result, keys, [], live_value, owned)
        ):
            result.merged[key] = foreign
            if _discards(live_value, foreign):
                result.overwritten[_dotted(keys)] = live_value
        else:
            result.removed.append(_dotted(keys))
    for key, repo_value in repo.items():
        if key not in live:
            result.merged[key] = repo_value
    return result


def _merge_list(
    result: Merge, keys: KeyPath, repo: list[Any], live: list[Any], owned: set[str]
) -> list[Any]:
    """Return the `live` list at `keys` in its own order, each element merged with the `repo`
    element of the same identity, followed by the `repo` elements `live` lacks.

    The k-th live element of an identity pairs with the k-th repo element of it, skipping a live
    object whose members are all another's (a group another tool added with no matcher, like the
    repo's), which is not the repo's object. A live element left unpaired whose identity `owned` holds keeps only the member elements the repo does not
    own, and goes when none is left; any other unpaired element is kept and reported."""
    unpaired: dict[str, list[Any]] = {}
    for element in repo:
        unpaired.setdefault(_identity(element), []).append(element)
    merged = []
    for element in live:
        identity = _identity(element)
        if unpaired.get(identity) and _holds_owned_member(keys, identity, element, owned):
            repo_element = unpaired[identity].pop(0)
            merged.append(_merge_element(result, keys, identity, repo_element, element, owned))
        elif _pointer((*keys, identity)) in owned:
            if (rest := _unowned_part(result, keys, identity, element, owned)) is not None:
                merged.append(rest)
        else:
            merged.append(element)
            result.kept.append(f"{_dotted(keys)} {_canonical(element)}")
    return merged + [element for left in unpaired.values() for element in left]


def _merge_element(
    result: Merge, keys: KeyPath, identity: str, repo: Any, live: Any, owned: set[str]
) -> Any:
    """Return the `live` element paired with `repo`: the repo's, with each member list merged."""
    if not isinstance(repo, dict):
        return repo
    live_members = _members(live)
    return {
        **repo,
        **{
            field: _merge_list(
                result, (*keys, identity, field), members, live_members[field], owned
            )
            for field, members in _members(repo).items()
            if field in live_members
        },
    }


def _unowned_part(result: Merge, keys: KeyPath, identity: str, live: Any, owned: set[str]) -> Any:
    """Return the `live` element the repo owns with only the member elements it does not own, or
    None when none is left."""
    members = {
        field: _merge_list(result, (*keys, identity, field), [], value, owned)
        for field, value in _members(live).items()
    }
    return {**live, **members} if any(members.values()) else None


def _holds_owned_member(keys: KeyPath, identity: str, element: Any, owned: set[str]) -> bool:
    """Whether `element` has no members or holds one that `owned` names."""
    members = _members(element)
    return not members or any(
        _pointer((*keys, identity, field, _identity(member))) in owned
        for field, values in members.items()
        for member in values
    )


def _members(element: Any) -> dict[str, list[Any]]:
    """Return the MEMBER_FIELDS of `element` that hold lists; none for an element not an object."""
    if not isinstance(element, dict):
        return {}
    return {f: v for f, v in element.items() if f in MEMBER_FIELDS and isinstance(v, list)}


def _discards(live_value: Any, value: Any) -> bool:
    """Whether merging replaced `live_value` with a `value` that lost some of it; reordering a
    list loses nothing, dropping a duplicate does."""
    if isinstance(live_value, list) and isinstance(value, list):
        return any(live_value.count(element) > value.count(element) for element in live_value)
    return live_value != value


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


def _identity(element: Any) -> str:
    """The canonical JSON of `element` without its member lists."""
    members = _members(element)
    if members:
        element = {k: v for k, v in element.items() if k not in members}
    return _canonical(element)


def _canonical(element: Any) -> str:
    return json.dumps(element, sort_keys=True)


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
    kinds: Record, repo: Path, shipped: dict[str, Callable[[Settings], set[str]]]
) -> dict[str, set[str]]:
    """Return the entries of each kind in `shipped` recorded in `kinds`, standing in for a kind
    missing from it with what that kind's function finds in every committed version of `repo`."""
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
    record = read_record(args.record)
    recorded = _recorded(
        record, args.repo, {SETTINGS_KIND: shipped_paths, ELEMENTS_KIND: shipped_elements}
    )
    dropped = retired(recorded[SETTINGS_KIND], paths)
    original = args.live.read_bytes() if args.live.exists() else None
    live = {} if original is None else _parse_live(args.live, original)
    result = merge(repo, live or {}, dropped, recorded[ELEMENTS_KIND])
    if original is not None and (live is None or result.overwritten or result.removed):
        _back_up(args.live, original)
    write_json_atomically(args.live, result.merged)

    previously_kept = set(record.get(KEPT_KIND, []))
    for path in result.kept:
        if path not in previously_kept:
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
    # Recorded only after the reports, so a run that dies before reporting a kept setting
    # reports it next time.
    write_kinds(
        args.record,
        {SETTINGS_KIND: paths, ELEMENTS_KIND: elements, KEPT_KIND: set(result.kept)},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
