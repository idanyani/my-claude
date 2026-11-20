"""Tests for the command splitting and the fail-closed answer the Bash-gating hooks share."""

import io
import json

import pytest
from bash_commands import gh_issue_create_args, run_gate, simple_commands


def creates_an_issue(command: str) -> bool:
    return any(gh_issue_create_args(words) is not None for words in simple_commands(command))


class TestGhIssueCreate:
    @pytest.mark.parametrize(
        "command",
        [
            "BODY=x; gh issue create --title x",
            "FOO=1 && gh issue create --title x",
            "timeout 60 gh issue create --title x",
            "nohup gh issue create --title x",
            "time gh issue create --title x",
            "exec gh issue create --title x",
            "sudo -E gh issue create --title x",
            "env -i gh issue create --title x",
            "/usr/bin/env gh issue create --title x",
            "sudo -u bob gh issue create --title x",
            "timeout -s KILL 60 gh issue create --title x",
            "command gh issue create --title x",
            "xargs gh issue create --title x",
            "echo `gh issue create --title x`",
            "sh -c 'gh issue create --title x'",
            "zsh -c 'gh issue create --title x'",
            "env FOO=1 bash -c 'gh issue create --title x'",
            "timeout 60 sh -c 'gh issue create --title x'",
        ],
    )
    def test_finds_an_issue_create_however_it_is_launched(self, command):
        assert creates_an_issue(command)

    @pytest.mark.parametrize("command", ["FOO=1", "env", "bash -c", "gh issue list", "ls"])
    def test_finds_none_in_other_commands(self, command):
        assert not creates_an_issue(command)

    def test_gives_the_words_after_gh(self):
        assert gh_issue_create_args(["sudo", "-u", "bob", "gh", "issue", "create", "-l", "x"]) == [
            "issue",
            "create",
            "-l",
            "x",
        ]


class TestRunGate:
    def run(self, monkeypatch, stdin: str, refusal) -> dict | None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        out = io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        assert run_gate(refusal, "Cannot check X") == 0
        return json.loads(out.getvalue())["hookSpecificOutput"] if out.getvalue() else None

    def test_stays_silent_when_there_is_no_reason(self, monkeypatch):
        assert self.run(monkeypatch, "{}", lambda payload: None) is None

    def test_denies_with_the_reason(self, monkeypatch):
        decision = self.run(monkeypatch, "{}", lambda payload: "no")
        assert decision == {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "no",
        }

    def test_denies_naming_what_it_could_not_check(self, monkeypatch):
        decision = self.run(monkeypatch, "not json", lambda payload: None)
        assert decision is not None
        assert decision["permissionDecision"] == "deny"
        assert decision["permissionDecisionReason"].startswith("Cannot check X: ")
