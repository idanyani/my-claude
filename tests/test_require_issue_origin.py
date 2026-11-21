"""Tests for the hook that sends every issue filing through file-issue's script."""

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
            "gh issue create --title x",
            "gh issue create --title x --label origin:developer",
            "cd repo && gh issue create --title x",
        ],
    )
    def test_refuses_filing_an_issue_directly(self, command):
        reason = refusal(bash(command))
        assert reason is not None
        assert "file_issue.py" in reason

    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.claude/skills/file-issue/scripts/file_issue.py --origin agent --title x",
            "gh issue create --help",
            "gh issue list --label bug",
            "ls",
        ],
    )
    def test_lets_other_commands_through(self, command):
        assert refusal(bash(command)) is None


class TestHookProcess:
    def test_stays_silent_on_a_command_that_files_no_issue(self):
        result = run_hook(HOOK, json.dumps(bash("ls")))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_filing_an_issue_directly(self):
        result = run_hook(HOOK, json.dumps(bash("gh issue create --title x")))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert (decision["hookEventName"], decision["permissionDecision"]) == ("PreToolUse", "deny")

    def test_denies_when_its_input_is_not_json(self):
        output = json.loads(run_hook(HOOK, "not json").stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
