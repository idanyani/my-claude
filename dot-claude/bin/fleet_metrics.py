#!/usr/bin/env python3
"""Measure the fleet's outcomes per unit of the developer's attention.

Usage:
  python3 ~/.claude/bin/fleet_metrics.py collect <store>
  python3 ~/.claude/bin/fleet_metrics.py report <store> [--weeks N]

`<store>` is a clone of a private repo that holds the counts. Session transcripts stay on the
machine that ran them and Claude Code deletes them after a month, so `collect`, run daily on each
machine, saves the developer's turns per day and repo into `turns/<host>.csv` there, commits, and
pushes. A count only grows: a day whose older transcripts expired keeps the count saved before.

A turn is a message the developer typed, or a slash command; task notifications, compaction
summaries, and the messages Claude Code adds itself are not turns. A session's repo is the GitHub
remote of the directory it ran in; a session outside any repo counts under `-`.

`report` reads every machine's turns and, from GitHub, the issues labeled `origin:developer` in
the repos the turns name: an issue lands when it is closed as completed, counts once it has stood
`LANDING_DAYS` days, and is pending until then. Beside those it shows the reopenings of such issues
and the commits on each default branch that revert another, the rates that would show a gain in
landings per turn bought by work that did not hold.

Stdlib-only: it needs just `python3`, `git`, and `gh` on PATH.
"""

import argparse
import csv
import json
import re
import socket
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NamedTuple

Key = tuple[str, str]

PROJECTS = Path.home() / ".claude" / "projects"
NO_REPO = "-"
LANDING_DAYS = 14
DEFAULT_WEEKS = 8
DEVELOPER_LABEL = "origin:developer"
GITHUB_REMOTE = re.compile(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$")
SLASH_COMMAND = "<command-name>"
REVERT_HEADLINE = 'Revert "'

ISSUES_QUERY = (
    """
query($owner: String!, $name: String!, $since: DateTime!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $endCursor, labels: ["%s"], filterBy: {since: $since}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        state stateReason closedAt
        timelineItems(itemTypes: [REOPENED_EVENT], first: 100) {
          nodes { ... on ReopenedEvent { createdAt } }
        }
      }
    }
  }
}
"""
    % DEVELOPER_LABEL
)

HISTORY_QUERY = """
query($owner: String!, $name: String!, $since: GitTimestamp!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $endCursor, since: $since) {
        pageInfo { hasNextPage endCursor }
        nodes { committedDate messageHeadline }
      }
    } } }
  }
}
"""


class WeekRow(NamedTuple):
    week: date
    turns: int
    landed: int
    pending: int
    reopened: int
    reverts: int


def is_developer_turn(entry: dict[str, Any]) -> bool:
    content = entry.get("message", {}).get("content")
    if entry.get("type") != "user" or entry.get("isMeta") or not isinstance(content, str):
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    # Some Claude Code versions log a slash command with no origin.
    return content.lstrip().startswith(SLASH_COMMAND)


def count_turns(lines: Iterable[str]) -> Counter[Key]:
    """Turns per (UTC day, directory), each entry once though a resumed session copies it."""
    seen: set[str] = set()
    counts: Counter[Key] = Counter()
    for line in lines:
        # Most of a transcript is tool output; parsing only what can be a turn keeps a month cheap.
        if "human" not in line and SLASH_COMMAND not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict) or not is_developer_turn(entry):
            continue
        if entry["uuid"] in seen:
            continue
        seen.add(entry["uuid"])
        counts[(entry["timestamp"][:10], entry["cwd"])] += 1
    return counts


def repo_slug(remote_url: str) -> str | None:
    match = GITHUB_REMOTE.search(remote_url.strip())
    # GitHub ignores case in owner and repo names, so one repo has one slug.
    return f"{match[1]}/{match[2]}".lower() if match else None


def merged_turns(old: dict[Key, int], new: dict[Key, int]) -> dict[Key, int]:
    return {key: max(old.get(key, 0), new.get(key, 0)) for key in old.keys() | new.keys()}


def _day(timestamp: str) -> date:
    return date.fromisoformat(timestamp[:10])


def issue_dates(nodes: list[dict[str, Any]]) -> tuple[list[date], list[date]]:
    """The days issues were closed as done, and the days they were reopened."""
    landed = [
        _day(node["closedAt"])
        for node in nodes
        if node["state"] == "CLOSED" and node["stateReason"] == "COMPLETED"
    ]
    reopened = [
        _day(event["createdAt"]) for node in nodes for event in node["timelineItems"]["nodes"]
    ]
    return landed, reopened


def revert_dates(nodes: list[dict[str, Any]]) -> list[date]:
    return [
        _day(node["committedDate"])
        for node in nodes
        if node["messageHeadline"].startswith(REVERT_HEADLINE)
    ]


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_rows(
    turns: dict[Key, int],
    landed: list[date],
    reopened: list[date],
    reverts: list[date],
    today: date,
    weeks: int,
) -> list[WeekRow]:
    """One row per week, Monday first, the last `weeks` weeks through the one holding `today`."""
    last = _monday(today)
    stood = today - timedelta(days=LANDING_DAYS)
    turns_by_week: Counter[date] = Counter()
    for (day, _), n in turns.items():
        turns_by_week[_monday(_day(day))] += n
    landed_by_week = Counter(_monday(day) for day in landed if day <= stood)
    pending_by_week = Counter(_monday(day) for day in landed if day > stood)
    reopened_by_week = Counter(map(_monday, reopened))
    reverts_by_week = Counter(map(_monday, reverts))
    return [
        WeekRow(
            start,
            turns_by_week[start],
            landed_by_week[start],
            pending_by_week[start],
            reopened_by_week[start],
            reverts_by_week[start],
        )
        for start in (last - timedelta(weeks=n) for n in reversed(range(weeks)))
    ]


def _run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def _repo_of(directory: str, cache: dict[str, str]) -> str:
    if directory not in cache:
        path = Path(directory)
        # A worktree a session ran in may since be gone; its repo still holds it.
        while not path.exists():
            path = path.parent
        try:
            slug = repo_slug(_run(["git", "-C", str(path), "remote", "get-url", "origin"]))
        except RuntimeError:
            slug = None
        cache[directory] = slug or NO_REPO
    return cache[directory]


def _read_turns(csv_file: Path) -> dict[Key, int]:
    if not csv_file.exists():
        return {}
    with csv_file.open(newline="", encoding="utf-8") as f:
        return {(row["date"], row["repo"]): int(row["turns"]) for row in csv.DictReader(f)}


def _write_turns(csv_file: Path, turns: dict[Key, int]) -> None:
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "repo", "turns"])
        writer.writerows([day, repo, n] for (day, repo), n in sorted(turns.items()))


def collect(store: Path, projects: Path, host: str) -> None:
    # A live session may be mid-way through appending a line, cut inside a character; only that
    # last line is broken, and count_turns skips it as JSON that does not parse.
    lines = (
        line
        for path in sorted(projects.glob("*/*.jsonl"))
        for line in path.open(encoding="utf-8", errors="replace")
    )
    cache: dict[str, str] = {}
    by_repo: Counter[Key] = Counter()
    for (day, directory), n in count_turns(lines).items():
        by_repo[(day, _repo_of(directory, cache))] += n
    csv_file = store / "turns" / f"{host}.csv"
    saved = _read_turns(csv_file)
    merged = merged_turns(saved, by_repo)
    if merged != saved:
        _write_turns(csv_file, merged)
        relative = str(csv_file.relative_to(store))
        _run(["git", "add", relative], cwd=store)
        _run(["git", "commit", "-q", "-m", f"Count {host}'s turns", relative], cwd=store)
    # Every run pushes, so a commit an earlier failed push left behind still reaches the store.
    # Each machine writes only its own file, so a rebase onto another machine's push is clean.
    if _run(["git", "ls-remote", "--heads", "origin"], cwd=store):
        _run(["git", "pull", "--rebase", "-q"], cwd=store)
    _run(["git", "push", "-q"], cwd=store)


def _graphql_nodes(query: str, jq: str, repo: str, **variables: str) -> list[dict[str, Any]]:
    owner, name = repo.split("/")
    args = ["gh", "api", "graphql", "--paginate", "-f", f"query={query}", "--jq", jq]
    # -f keeps every value a string; -F would turn a repo named 2048 into a number.
    for key, value in {"owner": owner, "name": name, **variables}.items():
        args += ["-f", f"{key}={value}"]
    return [json.loads(line) for line in _run(args).splitlines() if line]


def report(store: Path, today: date, weeks: int) -> list[WeekRow]:
    turns: Counter[Key] = Counter()
    for csv_file in sorted((store / "turns").glob("*.csv")):
        turns.update(_read_turns(csv_file))
    since = f"{_monday(today) - timedelta(weeks=weeks - 1)}T00:00:00Z"
    landed: list[date] = []
    reopened: list[date] = []
    reverts: list[date] = []
    for repo in sorted({repo for _, repo in turns} - {NO_REPO}):
        try:
            issues = _graphql_nodes(
                ISSUES_QUERY, ".data.repository.issues.nodes[]", repo, since=since
            )
            history = _graphql_nodes(
                HISTORY_QUERY,
                ".data.repository.defaultBranchRef.target.history.nodes[]",
                repo,
                since=since,
            )
        except RuntimeError as error:
            print(f"Left out {repo}: {error}", file=sys.stderr)
            continue
        repo_landed, repo_reopened = issue_dates(issues)
        landed += repo_landed
        reopened += repo_reopened
        reverts += revert_dates(history)
    return weekly_rows(turns, landed, reopened, reverts, today, weeks)


def format_rows(rows: list[WeekRow]) -> str:
    lines = ["week        turns  landed  pending  landed/100 turns  reopened  reverts"]
    for row in rows:
        rate = f"{100 * row.landed / row.turns:.1f}" if row.turns else "-"
        lines.append(
            f"{row.week}  {row.turns:5}  {row.landed:6}  {row.pending:7}  {rate:>16}"
            f"  {row.reopened:8}  {row.reverts:7}"
        )
    return "\n".join(lines)


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive number of weeks")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fleet_metrics.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("collect").add_argument("store", type=Path)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("store", type=Path)
    report_parser.add_argument("--weeks", type=_positive, default=DEFAULT_WEEKS)
    args = parser.parse_args(argv)
    if args.command == "collect":
        collect(args.store, PROJECTS, socket.gethostname())
    else:
        # Turns, closes, and commits are all dated in UTC.
        today = datetime.now(timezone.utc).date()
        print(format_rows(report(args.store, today, args.weeks)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
