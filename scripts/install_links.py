#!/usr/bin/env python3
"""Symlink the dot-claude/ tree into ~/.claude and retire links to entries the repo dropped.

The repo ships what git lists in dot-claude/ -- committed or not yet committed, but never
git-ignored, so a cache that outlives the tracked files around it does not keep an entry shipped.
A top-level file is linked whole and a top-level directory per child, so machine-local entries
can coexist beside the repo's; the entries install.sh merges instead are skipped. Linking again
is idempotent and heals links that point elsewhere, such as into a moved clone.

The links placed are kept in the install record (install_record.py) under the "links" kind, and
a recorded link the repo no longer ships is removed -- but only while it is still a symlink into
dot-claude/, so a machine-local file, or a link pointing elsewhere, at that path is never touched. With no "links" kind
in the record, the links into dot-claude/ already in ~/.claude stand in for it.

Usage: install_links.py <dot-claude-dir> <claude-dir> <record-file> [--merged NAME ...]
"""

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Collection
from pathlib import Path, PurePosixPath

from install_record import read_record, retired, write_kinds

LINKS_KIND = "links"


def planned_links(src: Path, merged: Collection[str]) -> dict[str, Path]:
    """Map each link path, relative to ~/.claude, to the entry of `src` it points to."""
    links: dict[str, Path] = {}
    for path in _shipped_files(src):
        if path.parts[0] in merged or any(part.startswith(".") for part in path.parts[:2]):
            continue
        name = PurePosixPath(*path.parts[:2])
        links[str(name)] = src / name
    return links


def links_into(dest: Path, src: Path) -> set[str]:
    """Return the symlinks into `src` at the depths an install creates them, relative to `dest`."""
    if not dest.is_dir():
        return set()
    found: set[str] = set()
    for entry in dest.iterdir():
        if entry.is_symlink():
            if is_link_into(entry, src):
                found.add(entry.name)
        elif entry.is_dir():
            found |= {
                f"{entry.name}/{child.name}"
                for child in entry.iterdir()
                if is_link_into(child, src)
            }
    return found


def is_link_into(link: Path, src: Path) -> bool:
    """Whether `link` is a symlink into `src`, live or dangling."""
    return link.is_symlink() and _points_into(link, src)


def install(src: Path, dest: Path, record: Path, merged: Collection[str]) -> None:
    recorded_kinds = read_record(record)
    recorded = (
        set(recorded_kinds[LINKS_KIND]) if LINKS_KIND in recorded_kinds else links_into(dest, src)
    )

    planned = planned_links(src, merged)
    placed = {name for name, target in planned.items() if _link(dest / name, target, src)}

    for name in retired(recorded, set(planned)):
        link = dest / name
        if is_link_into(link, src):
            link.unlink()
            print(f"removed {link}: {src} no longer ships its target", file=sys.stderr)
        elif link.exists() or link.is_symlink():
            print(f"left {link}: not a link into {src}", file=sys.stderr)

    write_kinds(record, {LINKS_KIND: placed})


def _shipped_files(src: Path) -> list[PurePosixPath]:
    """Return the files git lists under `src` that exist, relative to `src`."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=src,
        check=True,
        capture_output=True,
    ).stdout
    # --cached also lists committed files deleted from the working tree.
    names = (os.fsdecode(name) for name in listed.split(b"\0") if name)
    return [PurePosixPath(name) for name in names if os.path.lexists(src / name)]


def _points_into(link: Path, src: Path) -> bool:
    # The target may be gone, so it is normalized lexically rather than resolved.
    target = Path(os.path.normpath(link.parent / os.readlink(link)))
    return any(target.is_relative_to(root) for root in {Path(os.path.abspath(src)), src.resolve()})


def _link(path: Path, target: Path, src: Path) -> bool:
    """Point `path` at `target` atomically, replacing a file or link there; report success."""
    if path.is_symlink() and os.readlink(path) == str(target):
        return True
    # A parent that is itself a link into the repo (a repo file that became a directory) would
    # route the new link into the repo, overwriting the very file it points to.
    if path.parent.is_symlink() and _points_into(path.parent, src):
        path.parent.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    # tempfile has no mkstemp for symlinks; the name is only reserved by creating the link.
    tmp = Path(tempfile.mktemp(dir=path.parent, prefix=f".{path.name}", suffix=".tmp"))
    tmp.symlink_to(target)
    try:
        os.replace(tmp, path)
    except IsADirectoryError:
        print(f"left {path}: a directory is in the way of the link to {target}", file=sys.stderr)
        return False
    finally:
        tmp.unlink(missing_ok=True)
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("record", type=Path)
    parser.add_argument("--merged", action="append", default=[], metavar="NAME")
    args = parser.parse_args(argv)
    install(args.src, args.dest, args.record, args.merged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
