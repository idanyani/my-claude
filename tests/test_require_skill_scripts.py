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
        ("command", "refused", "skill", "script"),
        [
            ("gh issue create --title x", "gh issue create", "file-issue", "file_issue.py"),
            ("gh pr create --fill", "gh pr create", "resolve-issue", "open_pr.py"),
            ("gh pr merge 5 --squash", "gh pr merge", "resolve-issue", "finish_branch.py"),
        ],
    )
    def test_names_the_script_and_skill_to_use_instead(self, command, refused, skill, script):
        reason = refusal(bash(command)) or ""
        assert f"`{refused}`" in reason
        assert f"scripts/{script}" in reason
        assert f"skill: {skill}" in reason

    @pytest.mark.parametrize(
        "command",
        [
            "BODY=x; gh issue create --title x",
            "timeout -s KILL 60 gh issue create --title x",
            "nohup gh issue create --title x",
            "time gh issue create --title x",
            "exec gh issue create --title x",
            "sudo -E gh issue create --title x",
            "env -i gh issue create --title x",
            "/usr/bin/env gh issue create --title x",
            "command gh issue create --title x",
            "xargs gh issue create --title x",
            "GH_HOST=h gh issue create --title x",
            "/usr/bin/gh issue create --title x",
            "echo `gh issue create --title x`",
            "(cd x && gh issue create --title x)",
            "echo body | gh issue create --body-file -",
            'gh issue create --title "a | b; c"',
            "gh issue create --title 'unterminated",
            "cd x && gh issue create --title 'unterminated",
            "ls # check\ngh issue create --title x",
            "echo a#b\ngh issue create --title x",
            "zsh -c 'gh issue create --title x'",
            "env FOO=1 bash -c 'gh issue create --title x'",
            "timeout 60 sh -c 'gh issue create --title x'",
            "gh --repo=owner/repo issue create --title x",
            "uv run --with gh gh pr create --fill",
            "sudo -u gh gh pr merge 5 --squash",
            "sudo -u bob /usr/bin/gh pr merge 5",
            "gh -R o/r pr create --fill",
            "gh pr -R o/r merge 5",
            "gh pr view 5 && gh pr merge 5 --squash",
            "gh pr merge 5 --disable-auto; gh pr merge 5 --squash",
            "gh pr create --base wip --head x --draft",
            "gh pr merge 5 --auto --merge",
            "gh pr create --fill --disable-auto",
            "gh issue create --title x --disable-auto",
            "gh pr new --fill",
            "gh issue new --title x",
        ],
    )
    def test_refuses_the_direct_command_however_it_is_launched(self, command):
        assert refusal(bash(command)) is not None

    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.claude/skills/resolve-issue/scripts/finish_branch.py 5",
            "gh issue create --help",
            "gh pr create -h",
            "gh pr merge --help",
            "gh pr merge 5 --disable-auto",
            "gh pr view 5",
            "gh issue list --label bug",
            "FOO=1",
            "bash -c",
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
