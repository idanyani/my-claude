"""Tests for the hook that sends filing issues and opening and merging PRs through skill scripts."""

import json
from pathlib import Path

import pytest
from hook_process import run_hook
from require_skill_scripts import refusal

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "require_skill_scripts.py"


def bash(command: str) -> dict:
    return {"tool_input": {"command": command}}


class TestRefusal:
    @pytest.mark.parametrize(
        ("command", "script"),
        [
            ("gh issue create --title x", "file_issue.py"),
            ("gh issue create --title x --label origin:developer", "file_issue.py"),
            ("cd repo && gh issue create --title x", "file_issue.py"),
            ("gh pr create --fill", "open_pr.py"),
            ("gh pr create --base wip --head x --draft", "open_pr.py"),
            ("gh -R o/r pr create --fill", "open_pr.py"),
            ("gh pr merge 5 --squash --delete-branch", "finish_branch.py"),
            ("gh pr merge 5 --auto --merge", "finish_branch.py"),
        ],
    )
    def test_refuses_a_direct_command_naming_its_script(self, command, script):
        reason = refusal(bash(command))
        assert reason is not None
        assert script in reason

    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.claude/skills/file-issue/scripts/file_issue.py --origin agent --title x",
            "python3 ~/.claude/skills/resolve-issue/scripts/open_pr.py --no-footer",
            "python3 ~/.claude/skills/resolve-issue/scripts/finish_branch.py 5",
            "gh issue create --help",
            "gh pr create -h",
            "gh pr merge --help",
            "gh pr merge 5 --disable-auto",
            "gh pr view 5",
            "gh issue list --label bug",
            "ls",
        ],
    )
    def test_lets_other_commands_through(self, command):
        assert refusal(bash(command)) is None


class TestHookProcess:
    def test_stays_silent_on_a_command_it_does_not_gate(self):
        result = run_hook(HOOK, json.dumps(bash("ls")))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_a_direct_pr_merge(self):
        result = run_hook(HOOK, json.dumps(bash("gh pr merge 5 --squash")))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert (decision["hookEventName"], decision["permissionDecision"]) == ("PreToolUse", "deny")

    def test_denies_when_its_input_is_not_json(self):
        output = json.loads(run_hook(HOOK, "not json").stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
