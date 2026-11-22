"""Tests for the command splitting and the fail-closed answer the Bash-gating hooks share."""

import io
import json

import pytest
from bash_commands import gh_command, run_gate, simple_commands


def creates_an_issue(command: str) -> bool:
    return any(
        (found := gh_command(words)) is not None and found[0] == ("issue", "create")
        for words in simple_commands(command)
    )


class TestGhCommand:
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
            "gh issue create --title x --body-file /tmp/b",
            "gh -R owner/repo issue create --title x",
            "cd /repo && gh issue create --title x",
            'gh issue create --title "a | b; c"',
            "echo start\ngh issue create --title x",
            "gh issue create --title 'unterminated",
            "cd x && gh issue create --title 'unterminated",
            "gh --repo owner/repo issue create --title x",
            "gh --repo=owner/repo issue create --title x",
            "/usr/bin/gh issue create --title x",
            "env GH_HOST=h gh issue create --title x",
            "GH_HOST=h gh issue create --title x",
            "echo body | gh issue create --body-file -",
            "(cd x && gh issue create --title x)",
            "ls # check\ngh issue create --title x",
            "echo a#b\ngh issue create --title x",
            "sudo gh issue create --title x",
            "bash -c 'gh issue create --title x'",
        ],
    )
    def test_finds_an_issue_create_however_it_is_launched(self, command):
        assert creates_an_issue(command)

    @pytest.mark.parametrize("command", ["FOO=1", "env", "bash -c", "gh issue list", "ls"])
    def test_finds_none_in_other_commands(self, command):
        assert not creates_an_issue(command)

    def test_gives_the_subcommand_and_the_words_after_gh(self):
        words = ["sudo", "-u", "bob", "gh", "-R", "o/r", "pr", "merge", "5"]
        assert gh_command(words) == (("pr", "merge"), ["-R", "o/r", "pr", "merge", "5"])

    def test_gives_none_without_gh(self):
        assert gh_command(["git", "status"]) is None


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
