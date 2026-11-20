"""Tests for the hook that refuses filing an issue without a label naming where its work came from."""

import json
from pathlib import Path

import pytest
from hook_process import run_hook
from require_issue_origin import refusal

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "require_issue_origin.py"


def bash(command: str) -> dict:
    return {"tool_input": {"command": command}}


class TestRefusal:
    @pytest.mark.parametrize(
        "command",
        [
            "gh issue create --title x --label origin:developer",
            "gh issue create --title x -l origin:proposed",
            "gh issue create --title x --label=origin:agent",
            "gh issue create --title x --label bug,origin:agent",
            "gh issue create --title x --label bug --label origin:developer",
            "gh -R owner/repo issue create --title x --label origin:agent",
            "gh issue create --title x -lorigin:agent",
            "gh issue create --title x --label origin:agent --label origin:agent",
            "gh issue create --title x --label 'bug, origin:agent'",
            "gh issue create --help",
        ],
    )
    def test_allows_an_issue_with_one_origin(self, command):
        assert refusal(bash(command)) is None

    @pytest.mark.parametrize(
        "command",
        [
            "gh issue create --title x",
            "gh issue create --title x --label bug",
            "gh issue create --title x --label origin:someone",
            "gh issue create --title x --label origin:developer,origin:agent",
            "cd repo && gh issue create --title x",
            "bash -c 'gh issue create --title x'",
            "gh issue create --title 'unterminated",
            "gh issue create -l origin:agent -t x && gh issue create --title y",
            "gh issue list --label origin:agent && gh issue create --title x",
            "gh issue create --title x --label",
            "gh issue create --label --title origin:agent",
        ],
    )
    def test_refuses_an_issue_without_exactly_one_origin(self, command):
        assert refusal(bash(command)) is not None

    def test_the_refusal_names_every_origin_label(self):
        reason = refusal(bash("gh issue create --title x"))
        assert reason is not None
        for label in ("origin:developer", "origin:proposed", "origin:agent"):
            assert label in reason

    @pytest.mark.parametrize(
        "command",
        ["ls", "gh issue list --label bug", "gh issue edit 3 --add-label bug", "gh pr create"],
    )
    def test_other_commands_pass(self, command):
        assert refusal(bash(command)) is None


class TestHookProcess:
    def test_stays_silent_on_an_issue_with_an_origin(self):
        result = run_hook(HOOK, json.dumps(bash("gh issue create --title x --label origin:agent")))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_an_issue_without_an_origin(self):
        result = run_hook(HOOK, json.dumps(bash("gh issue create --title x")))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert (decision["hookEventName"], decision["permissionDecision"]) == ("PreToolUse", "deny")

    def test_denies_when_its_input_is_not_json(self):
        output = json.loads(run_hook(HOOK, "not json").stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
