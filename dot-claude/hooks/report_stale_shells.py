#!/usr/bin/env python3
"""SessionStart hook: report background shells that outlived the work they were started for.

A backgrounded command whose exit condition never arrives keeps its shell alive indefinitely,
and nothing in a fresh session mentions it -- the shells belong to the CLI process, not to the
conversation, so clearing the context leaves them running and invisible. This surfaces them at
the top of a session instead, so a leak shows up in minute one rather than after a workday.

It reports and never kills: the same shell may be a deliberate long-running watch, which only
the reader can judge.

Reading the process table is Linux-specific and best-effort; anywhere `/proc` is absent or
unreadable the hook stays silent rather than guessing.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

STALE_AFTER_SECONDS = 30 * 60

# The parent of every Claude-spawned background shell, as reported by /proc/<pid>/comm.
PARENT_COMMAND_NAME = "claude"

# Claude spawns MCP servers as well as background shells, and a server is long-lived by design.
# Selecting on the process name keeps those out of the report.
SHELL_COMMAND_NAMES = frozenset({"bash", "sh", "zsh", "dash"})

COMMAND_EXCERPT_LENGTH = 120


@dataclass(frozen=True)
class ShellProcess:
    pid: int
    cwd: str
    age_seconds: float
    command: str
    name: str


def select_stale(
    processes: list[ShellProcess], session_cwd: str, stale_after_seconds: float
) -> list[ShellProcess]:
    """Shells under `session_cwd` that have outlived `stale_after_seconds`, oldest first."""
    root = Path(session_cwd)
    stale = [
        process
        for process in processes
        if process.name in SHELL_COMMAND_NAMES
        and process.age_seconds > stale_after_seconds
        and Path(process.cwd).is_relative_to(root)
    ]
    return sorted(stale, key=lambda process: process.age_seconds, reverse=True)


def format_age(seconds: float) -> str:
    """Whole hours and minutes, e.g. `2h13m` or `47m`."""
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def format_report(stale: list[ShellProcess]) -> str:
    """Report naming each leftover shell, for the session's opening context."""
    lines = [
        "Background shells from an earlier session are still running in this directory. "
        "Stop the ones whose work is done (`/tasks`, or `kill <pid>`):"
    ]
    for process in stale:
        excerpt = process.command[:COMMAND_EXCERPT_LENGTH]
        if len(process.command) > COMMAND_EXCERPT_LENGTH:
            excerpt += "..."
        lines.append(f"  pid {process.pid}, running {format_age(process.age_seconds)}: {excerpt}")
    return "\n".join(lines)


def _read_child(pid: str, uptime_seconds: float, clock_ticks: int) -> ShellProcess | None:
    """The record for `pid` if its parent is a `claude` process, else None."""
    stat = Path("/proc", pid, "stat").read_text()
    # The comm field is parenthesized and may itself contain spaces or parens, so fields are
    # counted from the last ')': stat field N lands at index N - 3.
    fields = stat[stat.rindex(")") + 2 :].split()
    parent_pid, start_ticks = fields[1], int(fields[19])
    if Path("/proc", parent_pid, "comm").read_text().strip() != PARENT_COMMAND_NAME:
        return None
    return ShellProcess(
        pid=int(pid),
        cwd=str(Path("/proc", pid, "cwd").resolve()),
        age_seconds=uptime_seconds - start_ticks / clock_ticks,
        command=" ".join(Path("/proc", pid, "cmdline").read_text().split("\0")).strip(),
        name=Path("/proc", pid, "comm").read_text().strip(),
    )


def read_claude_children() -> list[ShellProcess]:
    """Every live process whose parent is a `claude` process. Empty where /proc is unavailable."""
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return []
    clock_ticks = os.sysconf("SC_CLK_TCK")
    children = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            child = _read_child(entry.name, uptime_seconds, clock_ticks)
        except (OSError, ValueError, IndexError):
            # The process exited mid-scan, or is one we may not inspect.
            continue
        if child is not None:
            children.append(child)
    return children


def main(argv: list[str]) -> int:
    payload = json.load(sys.stdin)
    session_cwd = payload.get("cwd")
    if not session_cwd:
        return 0
    stale = select_stale(read_claude_children(), session_cwd, STALE_AFTER_SECONDS)
    if stale:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": format_report(stale),
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level hook guard: never break session start
        print(error, file=sys.stderr)
        sys.exit(0)
