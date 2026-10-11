#!/usr/bin/env python3
"""Symlink the dot-claude/ tree into ~/.claude and retire links to entries the repo dropped.

Every top-level entry of dot-claude/ is handled by kind, so a new file or directory needs no
change here: a file is linked whole, and a directory is linked per child, so machine-local
entries can coexist beside the repo's. settings.json is merged by merge_settings.py instead.
Linking the same tree again is idempotent and heals links left by a moved clone.

The links installed are kept in the install record (install_record.py) under the "links" kind; a
recorded link the repo no longer ships is removed, but only while it is still a dangling symlink
into dot-claude/, so a machine-local file or link at that path is never touched. A machine with
no "links" record yet (installed before the record existed) is bootstrapped from the links into
dot-claude/ it already has.

Usage: install_links.py <dot-claude-dir> <claude-dir> <record-file>
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from install_record import read_record, retired, write_kind

LINKS_KIND = "links"
MERGED_ENTRIES = frozenset({"settings.json"})


def planned_links(src: Path) -> dict[str, Path]:
    """Map each link path, relative to ~/.claude, to the entry of `src` it points to."""
    links: dict[str, Path] = {}
    for entry in _visible_children(src):
        if entry.name in MERGED_ENTRIES:
            continue
        if entry.is_dir():
            for child in _visible_children(entry):
                links[f"{entry.name}/{child.name}"] = child
        else:
            links[entry.name] = entry
    return links


def links_into(dest: Path, src: Path) -> set[str]:
    """Return the symlinks into `src` at the depths an install creates them, relative to `dest`."""
    if not dest.is_dir():
        return set()
    found: set[str] = set()
    for entry in dest.iterdir():
        if entry.is_symlink():
            if _points_into(entry, src):
                found.add(entry.name)
        elif entry.is_dir():
            found |= {
                f"{entry.name}/{child.name}"
                for child in entry.iterdir()
                if child.is_symlink() and _points_into(child, src)
            }
    return found


def is_retirable(link: Path, src: Path) -> bool:
    """Whether `link` is a symlink into `src` whose target no longer exists."""
    return link.is_symlink() and not link.exists() and _points_into(link, src)


def install(src: Path, dest: Path, record: Path) -> None:
    planned = planned_links(src)
    for name, target in planned.items():
        _link(dest / name, target)

    recorded_kinds = read_record(record)
    recorded = (
        set(recorded_kinds[LINKS_KIND]) if LINKS_KIND in recorded_kinds else links_into(dest, src)
    )
    for name in retired(recorded, set(planned)):
        link = dest / name
        if is_retirable(link, src):
            link.unlink()
            print(f"removed {link}: its target left {src}", file=sys.stderr)
        elif link.exists() or link.is_symlink():
            print(f"left {link}: not a dangling link into {src}", file=sys.stderr)

    write_kind(record, LINKS_KIND, set(planned))


def _visible_children(directory: Path) -> list[Path]:
    # Hidden entries are skipped, as the shell glob `*` this replaced did.
    return sorted(p for p in directory.iterdir() if not p.name.startswith("."))


def _points_into(link: Path, src: Path) -> bool:
    # The target may be gone, so it is normalized lexically rather than resolved.
    target = Path(os.path.normpath(link.parent / os.readlink(link)))
    return any(target.is_relative_to(root) for root in {Path(os.path.abspath(src)), src.resolve()})


def _link(path: Path, target: Path) -> None:
    """Point `path` at `target`, replacing a file or link there, atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mktemp(dir=path.parent, prefix=f".{path.name}", suffix=".tmp"))
    tmp.symlink_to(target)
    try:
        os.replace(tmp, path)
    except IsADirectoryError:
        tmp.unlink()
        print(f"left {path}: a directory is in the way of the link to {target}", file=sys.stderr)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("record", type=Path)
    args = parser.parse_args(argv)
    install(args.src, args.dest, args.record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
