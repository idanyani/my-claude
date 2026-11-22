"""Tests for dot-claude/bin/fleet_metrics.py: transcript entries and GitHub nodes are built in each
test with only the fields the script reads."""

import json
from datetime import date
from pathlib import Path

import fleet_metrics
import pytest
from fleet_metrics import (
    WeekRow,
    collect,
    count_turns,
    format_rows,
    is_developer_turn,
    issue_dates,
    main,
    merged_turns,
    repo_slug,
    report,
    revert_dates,
    weekly_rows,
)
from git_repo import git, make_clone


def typed(text: str = "fix it", **extra) -> dict:
    return {"type": "user", "origin": {"kind": "human"}, "message": {"content": text}, **extra}


class TestIsDeveloperTurn:
    def test_a_message_the_developer_typed(self):
        assert is_developer_turn(typed())

    def test_a_slash_command_logged_without_an_origin(self):
        entry = {"type": "user", "message": {"content": " <command-name>/brief</command-name>"}}
        assert is_developer_turn(entry)

    @pytest.mark.parametrize(
        "entry",
        [
            typed(isMeta=True),
            {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": "x"}},
            {"type": "user", "isCompactSummary": True, "message": {"content": "summary"}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}},
            {"type": "assistant", "origin": {"kind": "human"}, "message": {"content": "x"}},
        ],
    )
    def test_anything_else(self, entry):
        assert not is_developer_turn(entry)


def line(entry: dict, uuid: str, timestamp: str, cwd: str) -> str:
    return json.dumps({**entry, "uuid": uuid, "timestamp": timestamp, "cwd": cwd})


class TestCountTurns:
    def test_counts_turns_per_utc_day_and_directory(self):
        lines = [
            line(typed(), "a", "2026-11-20T23:59:00.000Z", "/r/x"),
            line(typed(), "b", "2026-11-21T00:01:00.000Z", "/r/x"),
            line(typed(), "c", "2026-11-21T09:00:00.000Z", "/r/x"),
            line(typed(), "d", "2026-11-21T09:00:00.000Z", "/r/y"),
            line(typed(isMeta=True), "e", "2026-11-21T09:00:00.000Z", "/r/y"),
        ]
        assert count_turns(lines) == {
            ("2026-11-20", "/r/x"): 1,
            ("2026-11-21", "/r/x"): 2,
            ("2026-11-21", "/r/y"): 1,
        }

    def test_counts_an_entry_copied_into_another_transcript_once(self):
        entry = line(typed(), "a", "2026-11-21T09:00:00.000Z", "/r/x")
        assert count_turns([entry, entry]) == {("2026-11-21", "/r/x"): 1}

    def test_counts_a_slash_command_logged_without_an_origin(self):
        entry = {"type": "user", "message": {"content": "<command-name>/brief</command-name>"}}
        assert count_turns([line(entry, "a", "2026-11-21T09:00:00Z", "/r/x")]) == {
            ("2026-11-21", "/r/x"): 1
        }

    def test_skips_lines_that_are_not_json_objects(self):
        assert count_turns(["not json", "", '["human"]']) == {}


class TestRepoSlug:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/o/r.git",
            "https://github.com/o/r",
            "git@github.com:o/r.git",
            "ssh://git@github.com/o/r.git",
            "https://github.com/O/R.git",
        ],
    )
    def test_reads_owner_and_name_in_the_case_github_ignores(self, url):
        assert repo_slug(url) == "o/r"

    def test_a_remote_elsewhere_has_none(self):
        assert repo_slug("https://gitlab.com/o/r.git") is None


class TestMergedTurns:
    def test_keeps_the_larger_count_so_expired_transcripts_never_lower_it(self):
        old = {("2026-10-01", "o/r"): 5, ("2026-11-20", "o/r"): 3}
        new = {("2026-10-01", "o/r"): 2, ("2026-11-20", "o/r"): 4, ("2026-11-21", "o/r"): 1}
        assert merged_turns(old, new) == {
            ("2026-10-01", "o/r"): 5,
            ("2026-11-20", "o/r"): 4,
            ("2026-11-21", "o/r"): 1,
        }


def reopen(at: str) -> dict:
    return {"createdAt": at}


class TestIssueDates:
    def test_a_closed_completed_issue_lands_on_its_close_date(self):
        nodes = [
            {
                "state": "CLOSED",
                "stateReason": "COMPLETED",
                "closedAt": "2026-11-03T10:00:00Z",
                "timelineItems": {"nodes": []},
            }
        ]
        assert issue_dates(nodes) == ([date(2026, 11, 3)], [])

    @pytest.mark.parametrize(
        "node",
        [
            {"state": "CLOSED", "stateReason": "NOT_PLANNED", "closedAt": "2026-11-03T10:00:00Z"},
            {"state": "OPEN", "stateReason": None, "closedAt": None},
        ],
    )
    def test_an_issue_not_closed_as_done_does_not_land(self, node):
        assert issue_dates([{**node, "timelineItems": {"nodes": []}}]) == ([], [])

    def test_every_reopening_counts_on_its_own_date(self):
        nodes = [
            {
                "state": "OPEN",
                "stateReason": "REOPENED",
                "closedAt": "2026-11-03T10:00:00Z",
                "timelineItems": {
                    "nodes": [reopen("2026-11-04T08:00:00Z"), reopen("2026-11-09T08:00:00Z")]
                },
            }
        ]
        assert issue_dates(nodes) == ([], [date(2026, 11, 4), date(2026, 11, 9)])


class TestRevertDates:
    def test_counts_commits_that_revert_another(self):
        nodes = [
            {"committedDate": "2026-11-05T10:00:00Z", "messageHeadline": 'Revert "Add X (#7)"'},
            {"committedDate": "2026-11-05T11:00:00Z", "messageHeadline": "Reverting to plan A"},
            {"committedDate": "2026-11-06T11:00:00Z", "messageHeadline": "Add Y"},
        ]
        assert revert_dates(nodes) == [date(2026, 11, 5)]


class TestWeeklyRows:
    def test_sums_each_week_from_monday_and_marks_recent_landings_pending(self):
        turns = {("2026-11-09", "o/r"): 10, ("2026-11-15", "o/p"): 5, ("2026-11-17", "o/r"): 4}
        rows = weekly_rows(
            turns,
            landed=[date(2026, 11, 10), date(2026, 11, 18)],
            reopened=[date(2026, 11, 11)],
            reverts=[date(2026, 11, 19)],
            today=date(2026, 11, 21),
            weeks=2,
        )
        assert rows == [
            WeekRow(date(2026, 11, 9), turns=15, landed=0, pending=1, reopened=1, reverts=0),
            WeekRow(date(2026, 11, 16), turns=4, landed=0, pending=1, reopened=0, reverts=1),
        ]

    def test_a_landing_counts_once_it_has_stood_fourteen_days(self):
        rows = weekly_rows(
            {},
            landed=[date(2026, 11, 7), date(2026, 11, 8)],
            reopened=[],
            reverts=[],
            today=date(2026, 11, 21),
            weeks=3,
        )
        assert rows == [
            WeekRow(date(2026, 11, 2), turns=0, landed=1, pending=1, reopened=0, reverts=0),
            WeekRow(date(2026, 11, 9), turns=0, landed=0, pending=0, reopened=0, reverts=0),
            WeekRow(date(2026, 11, 16), turns=0, landed=0, pending=0, reopened=0, reverts=0),
        ]


class TestFormatRows:
    def test_shows_landings_per_hundred_turns_and_a_dash_for_a_week_without_turns(self):
        rows = [
            WeekRow(date(2026, 11, 2), turns=40, landed=1, pending=2, reopened=3, reverts=4),
            WeekRow(date(2026, 11, 9), turns=0, landed=0, pending=0, reopened=0, reverts=0),
        ]
        assert format_rows(rows).splitlines() == [
            "week        turns  landed  pending  landed/100 turns  reopened  reverts",
            "2026-11-02     40       1        2               2.5         3        4",
            "2026-11-09      0       0        0                 -         0        0",
        ]


class TestGraphqlNodes:
    def test_pages_through_every_result_and_reads_one_node_per_line(self, monkeypatch):
        calls = []

        def run(args, cwd=None):
            calls.append(args)
            return '{"a": 1}\n{"a": 2}\n'

        monkeypatch.setattr(fleet_metrics, "_run", run)
        assert fleet_metrics._graphql_nodes("Q", ".x[]", "o/r", since="S") == [{"a": 1}, {"a": 2}]
        [args] = calls
        assert args[:4] == ["gh", "api", "graphql", "--paginate"]
        assert args[args.index("--jq") + 1] == ".x[]"
        assert {args[i + 1] for i, arg in enumerate(args) if arg == "-f"} - {"query=Q"} == {
            "owner=o",
            "name=r",
            "since=S",
        }


class TestMain:
    def test_refuses_fewer_than_one_week(self, tmp_path):
        with pytest.raises(SystemExit):
            main(["report", str(tmp_path), "--weeks", "0"])

    def test_reports_the_default_number_of_weeks(self, tmp_path, monkeypatch, capsys):
        asked = []
        monkeypatch.setattr(
            fleet_metrics, "report", lambda store, today, weeks: asked.append(weeks) or []
        )
        assert main(["report", str(tmp_path)]) == 0
        assert asked == [8]

    def test_collects_into_the_given_store(self, tmp_path, monkeypatch):
        stores = []
        monkeypatch.setattr(
            fleet_metrics, "collect", lambda store, projects, host: stores.append(store)
        )
        assert main(["collect", str(tmp_path)]) == 0
        assert stores == [tmp_path]


@pytest.fixture
def git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "t")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "t@t")


def session(projects: Path, cwd: Path, *timestamps: str) -> None:
    project = projects / "p"
    project.mkdir(parents=True, exist_ok=True)
    lines = [line(typed(), f"{cwd}-{t}", t, str(cwd)) for t in timestamps]
    (project / f"{len(list(project.iterdir()))}.jsonl").write_text("\n".join(lines) + "\n")


class TestCollect:
    def test_saves_turns_per_day_and_repo_and_pushes_them(self, tmp_path, git_identity):
        store = make_clone(tmp_path, "main")
        repo = tmp_path / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", "https://github.com/o/r.git")
        projects = tmp_path / "projects"
        session(projects, repo / ".claude" / "worktrees" / "gone", "2026-11-20T10:00:00Z")
        session(projects, repo, "2026-11-20T10:30:00Z")
        session(projects, tmp_path, "2026-11-20T11:00:00Z", "2026-11-21T11:00:00Z")

        collect(store, projects, "box")

        assert (store / "turns" / "box.csv").read_text().splitlines() == [
            "date,repo,turns",
            "2026-11-20,-,1",
            "2026-11-20,o/r,2",
            "2026-11-21,-,1",
        ]
        assert git(store, "log", "-1", "--format=%s", "origin/main") == "Count box's turns"

    def test_keeps_counts_whose_transcripts_expired_and_commits_nothing_new(
        self, tmp_path, git_identity
    ):
        store = make_clone(tmp_path, "main")
        projects = tmp_path / "projects"
        session(projects, tmp_path, "2026-11-20T11:00:00Z")
        collect(store, projects, "box")
        head = git(store, "rev-parse", "HEAD")
        for transcript in (projects / "p").iterdir():
            transcript.unlink()

        collect(store, projects, "box")

        assert (store / "turns" / "box.csv").read_text().splitlines()[1:] == ["2026-11-20,-,1"]
        assert git(store, "rev-parse", "HEAD") == head

    def test_pushes_after_another_machine_pushed_its_own_counts(self, tmp_path, git_identity):
        store = make_clone(tmp_path, "main")
        other = tmp_path / "other"
        git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
        projects = tmp_path / "projects"
        session(projects, tmp_path, "2026-11-20T11:00:00Z")
        collect(other, projects, "laptop")

        collect(store, projects, "box")

        assert git(store, "ls-tree", "--name-only", "origin/main", "turns/").splitlines() == [
            "turns/box.csv",
            "turns/laptop.csv",
        ]

    def test_pushes_counts_a_failed_push_left_behind(self, tmp_path, git_identity):
        store = make_clone(tmp_path, "main")
        projects = tmp_path / "projects"
        session(projects, tmp_path, "2026-11-20T11:00:00Z")
        origin = str(tmp_path / "origin.git")
        git(store, "remote", "set-url", "origin", str(tmp_path / "unreachable"))
        with pytest.raises(RuntimeError):
            collect(store, projects, "box")
        git(store, "remote", "set-url", "origin", origin)

        collect(store, projects, "box")

        assert git(store, "ls-tree", "--name-only", "origin/main", "turns/") == "turns/box.csv"

    def test_reads_a_transcript_whose_last_line_is_still_being_written(
        self, tmp_path, git_identity
    ):
        store = make_clone(tmp_path, "main")
        projects = tmp_path / "projects"
        session(projects, tmp_path, "2026-11-20T11:00:00Z")
        transcript = next((projects / "p").iterdir())
        with transcript.open("ab") as f:
            f.write('{"message": {"content": "ש'.encode()[:-1])

        collect(store, projects, "box")

        assert (store / "turns" / "box.csv").read_text().splitlines()[1:] == ["2026-11-20,-,1"]

    def test_makes_the_first_push_to_an_empty_store(self, tmp_path, git_identity):
        origin = tmp_path / "origin.git"
        git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
        store = tmp_path / "store"
        git(tmp_path, "clone", "-q", str(origin), str(store))
        projects = tmp_path / "projects"
        session(projects, tmp_path, "2026-11-20T11:00:00Z")

        collect(store, projects, "box")

        assert git(origin, "ls-tree", "--name-only", "main", "turns/") == "turns/box.csv"


class TestReport:
    def test_counts_every_machines_turns_against_each_repos_github_record(
        self, tmp_path, monkeypatch, capsys
    ):
        turns = tmp_path / "turns"
        turns.mkdir()
        (turns / "a.csv").write_text("date,repo,turns\n2026-11-02,o/r,3\n2026-11-03,-,2\n")
        (turns / "b.csv").write_text("date,repo,turns\n2026-11-04,o/p,5\n")
        answers = {
            ("o/r", fleet_metrics.ISSUES_QUERY): [
                {
                    "state": "CLOSED",
                    "stateReason": "COMPLETED",
                    "closedAt": "2026-11-03T10:00:00Z",
                    "timelineItems": {"nodes": [{"createdAt": "2026-11-02T10:00:00Z"}]},
                }
            ],
            ("o/r", fleet_metrics.HISTORY_QUERY): [
                {"committedDate": "2026-11-04T10:00:00Z", "messageHeadline": 'Revert "X"'}
            ],
        }
        asked = []

        def nodes(query, jq, repo, **variables):
            asked.append((repo, variables))
            if repo == "o/p":
                raise RuntimeError("no access")
            return answers[(repo, query)]

        monkeypatch.setattr(fleet_metrics, "_graphql_nodes", nodes)
        monkeypatch.setattr(fleet_metrics, "_can_push", lambda repo: True)

        rows = report(tmp_path, date(2026, 11, 21), weeks=3)

        assert rows[0] == WeekRow(
            date(2026, 11, 2), turns=10, landed=1, pending=0, reopened=1, reverts=1
        )
        assert asked == [
            ("o/p", {"since": "2026-11-02T00:00:00Z"}),
            ("o/r", {"since": "2026-11-02T00:00:00Z"}),
            ("o/r", {"since": "2026-11-02T00:00:00Z"}),
        ]
        assert "Left out o/p: no access" in capsys.readouterr().err

    def test_counts_no_reverts_in_a_repo_the_session_cannot_push_to(self, tmp_path, monkeypatch):
        (tmp_path / "turns").mkdir()
        (tmp_path / "turns" / "a.csv").write_text("date,repo,turns\n2026-11-02,up/stream,3\n")
        queries = []

        def nodes(query, jq, repo, **variables):
            queries.append(query)
            return []

        monkeypatch.setattr(fleet_metrics, "_graphql_nodes", nodes)
        monkeypatch.setattr(fleet_metrics, "_can_push", lambda repo: False)

        report(tmp_path, date(2026, 11, 21), weeks=1)

        assert queries == [fleet_metrics.ISSUES_QUERY]

    @pytest.mark.parametrize(("permission", "expected"), [("WRITE", True), ("READ", False)])
    def test_can_push_reads_the_sessions_permission(self, monkeypatch, permission, expected):
        monkeypatch.setattr(fleet_metrics, "_run", lambda args, cwd=None: permission + "\n")
        assert fleet_metrics._can_push("o/r") is expected

    def test_a_store_without_turns_reports_empty_weeks_and_asks_github_nothing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(fleet_metrics, "_graphql_nodes", None)
        assert report(tmp_path, date(2026, 11, 21), weeks=1) == [
            WeekRow(date(2026, 11, 16), turns=0, landed=0, pending=0, reopened=0, reverts=0)
        ]
