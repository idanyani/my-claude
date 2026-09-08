"""Tests for the leftover-background-shell report.

The selection logic takes plain records so it tests without `/proc`; reading the process table
is the hook's I/O boundary and is exercised only through the file contract below.
"""

from pathlib import Path

from report_stale_shells import (
    STALE_AFTER_SECONDS,
    ShellProcess,
    format_report,
    select_stale,
)

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "report_stale_shells.py"

PROJECT = "/home/dev/repos/project"


def shell(
    pid: int,
    age_seconds: float,
    cwd: str = PROJECT,
    command: str = "sleep 15",
    name: str = "bash",
) -> ShellProcess:
    return ShellProcess(pid=pid, cwd=cwd, age_seconds=age_seconds, command=command, name=name)


class TestSelectStale:
    def test_reports_a_shell_older_than_the_threshold(self):
        (stale,) = select_stale([shell(1, 3600)], PROJECT, STALE_AFTER_SECONDS)
        assert stale.pid == 1

    def test_ignores_a_young_shell(self):
        assert select_stale([shell(1, 5)], PROJECT, STALE_AFTER_SECONDS) == []

    def test_threshold_is_exclusive_of_exactly_the_cutoff(self):
        assert select_stale([shell(1, 60)], PROJECT, 60) == []
        assert select_stale([shell(1, 61)], PROJECT, 60) != []

    def test_ignores_a_shell_from_another_project(self):
        assert select_stale([shell(1, 3600, cwd="/home/dev/repos/other")], PROJECT, 60) == []

    def test_includes_a_shell_in_a_subdirectory_of_the_project(self):
        (stale,) = select_stale([shell(1, 3600, cwd=f"{PROJECT}/lib")], PROJECT, 60)
        assert stale.pid == 1

    def test_a_sibling_with_a_shared_name_prefix_is_not_a_subdirectory(self):
        assert select_stale([shell(1, 3600, cwd=f"{PROJECT}-fork")], PROJECT, 60) == []

    def test_ignores_a_long_lived_mcp_server(self):
        # MCP servers are also children of `claude` and outlive any threshold by design.
        server = shell(1, 90000, command="npm exec @playwright/mcp@latest", name="npm exec @playw")
        assert select_stale([server], PROJECT, STALE_AFTER_SECONDS) == []

    def test_recognizes_the_common_shell_names(self):
        shells = [shell(i, 3600, name=n) for i, n in enumerate(("bash", "sh", "zsh", "dash"))]
        assert len(select_stale(shells, PROJECT, 60)) == len(shells)

    def test_a_symlinked_session_path_still_matches(self, tmp_path):
        # /proc reports a resolved cwd, so an unresolved session path would match nothing.
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        (stale,) = select_stale([shell(1, 3600, cwd=str(real))], str(link), 60)
        assert stale.pid == 1

    def test_orders_oldest_first(self):
        selected = select_stale([shell(1, 100), shell(2, 9000), shell(3, 500)], PROJECT, 60)
        assert [s.pid for s in selected] == [2, 3, 1]


class TestFormatReport:
    def test_names_each_pid_its_age_and_its_command(self):
        report = format_report([shell(4242, 7200, command="until ! pgrep -f x; do sleep 15; done")])
        assert "4242" in report
        assert "2h" in report
        assert "until ! pgrep" in report

    def test_shows_the_real_command_not_the_wrapper_preamble(self):
        # Every Claude shell shares a ~200-char snapshot-sourcing preamble; an excerpt of that
        # is identical for all of them and identifies nothing.
        wrapper = (
            "/bin/bash -c source /home/dev/.claude/shell-snapshots/snapshot-bash-1.sh "
            "2>/dev/null || true && shopt -u extglob 2>/dev/null || true && "
            "eval 'until ! pgrep -f x; do sleep 15; done'"
        )
        report = format_report([shell(7, 3600, command=wrapper)])
        assert "until ! pgrep -f x" in report
        assert "shell-snapshots" not in report

    def test_does_not_claim_the_shells_belong_to_an_earlier_session(self):
        # SessionStart also fires on resume, compact and clear, where the shells are the
        # current session's own and may still be doing the work they were started for.
        assert "earlier session" not in format_report([shell(1, 3600)])

    def test_truncates_a_long_command(self):
        report = format_report([shell(1, 3600, command="x" * 500)])
        assert max(len(line) for line in report.splitlines()) < 200


class TestHookFileContract:
    def test_carries_a_python3_shebang(self):
        assert HOOK.read_text().startswith("#!/usr/bin/env python3\n")

    def test_is_executable(self):
        assert HOOK.stat().st_mode & 0o111

    def test_source_is_pure_ascii(self):
        assert HOOK.read_bytes().isascii()
