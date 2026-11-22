"""Tests for the command splitting and the fail-closed answer the Bash-gating hooks share."""

import io
import json

from bash_commands import gh_commands, run_gate


class TestGhCommands:
    def test_gives_the_subcommand_and_the_words_after_gh(self):
        words = ["gh", "-R", "o/r", "pr", "merge", "5"]
        assert gh_commands(words) == [(("pr", "merge"), ["-R", "o/r", "pr", "merge", "5"])]

    def test_skips_the_values_of_gh_flags_between_the_subcommand_words(self):
        assert gh_commands(["gh", "pr", "--repo", "o/r", "merge", "5"])[0][0] == ("pr", "merge")

    def test_gives_every_word_that_may_be_the_gh_program(self):
        words = ["-u", "gh", "/usr/bin/gh", "pr", "merge"]
        assert [sub for sub, _ in gh_commands(words)] == [("/usr/bin/gh", "pr"), ("pr", "merge")]

    def test_gives_none_without_gh(self):
        assert gh_commands(["git", "status"]) == []


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
