"""The record of what install.sh placed in ~/.claude, so a later install can retire it.

An install only adds and refreshes what the repo ships; on its own it cannot tell an entry the
repo dropped from one the machine owns. Each installer step therefore records the entries it
installed under its own kind (one JSON list per kind, e.g. "links"), and on the next run retires
the recorded entries the repo no longer ships. How to retire an entry is the kind's own business,
and it must leave anything it cannot prove it installed untouched. A step may also record, under a
kind of its own, a condition it reported, so a later install reports only what is new.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

Record = dict[str, list[str]]

NEW_FILE_MODE = 0o644


def retired(recorded: set[str], shipped: set[str]) -> list[str]:
    """Return the recorded entries the repo no longer ships, sorted."""
    return sorted(recorded - shipped)


def read_record(path: Path) -> Record:
    """Return the record, or an empty one when the file is missing or unreadable."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(record, dict):
        return {}
    # Drop only a malformed kind, so one kind's damage never erases another's entries.
    return {
        kind: entries
        for kind, entries in record.items()
        if isinstance(entries, list) and all(isinstance(e, str) for e in entries)
    }


def write_kinds(path: Path, kinds: dict[str, set[str]]) -> None:
    """Replace the entries recorded under each kind in `kinds`, keeping every other kind's."""
    record = read_record(path)
    record.update({kind: sorted(entries) for kind, entries in kinds.items()})
    write_json_atomically(path, record)


def write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    """Write `data` as JSON so a reader never sees a partial file."""
    write_atomically(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode())


def write_atomically(path: Path, content: bytes, mode: int | None = None) -> None:
    """Write `content` so a reader never sees a partial file, with `mode` or else the file's own.

    A file that already holds `content` with `mode` is left in place: replacing it would still
    signal a change to everything watching it."""
    # Resolve so a symlinked file is updated through its link rather than replaced.
    target = path.resolve()
    current_mode = target.stat().st_mode & 0o777 if target.exists() else None
    if mode is None:
        # mkstemp creates the file owner-only; keep the mode the file had, as `cp` did.
        mode = NEW_FILE_MODE if current_mode is None else current_mode
    if current_mode == mode and _holds(target, content):
        return
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        os.unlink(tmp)
        raise


def _holds(path: Path, content: bytes) -> bool:
    """Whether `path` holds `content`; a file it cannot read is taken not to."""
    try:
        return path.read_bytes() == content
    except OSError:
        return False
