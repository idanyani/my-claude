"""Tests for the hook that refuses a skill's gated command unless the session's load of it is fresh.

Transcript entries are built in each test with only the fields the hook reads.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from require_fresh_skill import (
    Staleness,
    gated_skill,
    refusal,
    skill_files_changed_at,
    staleness,
    transcript_of,
)

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "require_fresh_skill.py"

T1 = "2026-11-17T18:16:00.000Z"
T2 = "2026-11-17T20:15:00.000Z"
BETWEEN = datetime(2026, 11, 17, 19, 0, tzinfo=UTC)
BEFORE = datetime(2026, 11, 17, 18, 0, tzinfo=UTC)


def skill_tool_load(skill: str, timestamp: str = T1) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]},
    }


def slash_command_load(skill: str, timestamp: str = T1) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {
            "content": f"<command-name>/{skill}</command-name>\n<command-args>7</command-args>"
        },
    }


def compaction(timestamp: str) -> dict[str, Any]:
    return {"type": "system", "subtype": "compact_boundary", "timestamp": timestamp}


class TestGatedSkill:
    @pytest.mark.parametrize(
        "command",
        [
            "gh issue create --title x --body-file /tmp/b",
            "gh -R owner/repo issue create --title x",
            "cd /repo && gh issue create --title x",
            'gh issue create --title "a | b; c"',
            "echo start\ngh issue create --title x",
            "gh issue create --title 'unterminated",
        ],
    )
    def test_filing_an_issue_needs_file_issue(self, command):
        assert gated_skill(command) == "file-issue"

    @pytest.mark.parametrize(
        "command",
        [
            "python3 /home/u/.claude/skills/resolve-issue/scripts/open_pr.py --footer x",
            "python3 /home/u/.claude/skills/resolve-issue/scripts/finish_branch.py 12",
            "git switch 7-x && python /s/scripts/finish_branch.py 7",
        ],
    )
    def test_the_pr_scripts_need_resolve_issue(self, command):
        assert gated_skill(command) == "resolve-issue"

    @pytest.mark.parametrize(
        "command",
        [
            "gh issue list --state open",
            "gh issue view 3",
            'grep -n "gh issue create" README.md',
            "uv run pytest tests/test_open_pr.py",
            "git add dot-claude/skills/resolve-issue/scripts/finish_branch.py",
            'git commit -m "Run finish_branch.py after open_pr.py"',
            "python3 dot-claude/skills/resolve-issue/scripts/start_branch.py 7 x",
            "echo 'unterminated",
        ],
    )
    def test_other_commands_are_not_gated(self, command):
        assert gated_skill(command) is None


class TestTranscriptOf:
    def test_the_main_session_reads_its_own_transcript(self):
        payload = {"transcript_path": "/p/abc.jsonl"}
        assert transcript_of(payload) == Path("/p/abc.jsonl")

    def test_a_subagent_reads_its_own_sidechain_transcript(self):
        payload = {"transcript_path": "/p/abc.jsonl", "agent_id": "def456"}
        assert transcript_of(payload) == Path("/p/abc/subagents/agent-def456.jsonl")


class TestSkillFilesChangedAt:
    def test_is_the_newest_file_anywhere_in_the_skill(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "SKILL.md").write_text("x")
        (tmp_path / "scripts" / "run.py").write_text("x")
        os.utime(tmp_path / "SKILL.md", (1000, 1000))
        os.utime(tmp_path / "scripts" / "run.py", (2000, 2000))
        assert skill_files_changed_at(tmp_path) == datetime.fromtimestamp(2000, UTC)

    def test_ignores_bytecode_running_the_scripts_writes(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("x")
        os.utime(tmp_path / "SKILL.md", (1000, 1000))
        cache = tmp_path / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "run.cpython-312.pyc").write_text("x")
        (tmp_path / "scripts" / "stray.pyc").write_text("x")
        assert skill_files_changed_at(tmp_path) == datetime.fromtimestamp(1000, UTC)

    def test_a_missing_skill_raises(self, tmp_path):
        with pytest.raises(OSError):
            skill_files_changed_at(tmp_path / "absent")


class TestStaleness:
    def test_a_session_that_never_loaded_the_skill(self):
        assert staleness([], "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_a_load_of_another_skill_does_not_count(self):
        entries = [skill_tool_load("file-issue")]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_a_skill_tool_load_newer_than_the_files_is_fresh(self):
        assert staleness([skill_tool_load("resolve-issue")], "resolve-issue", BEFORE) is None

    def test_a_slash_command_load_counts(self):
        assert staleness([slash_command_load("resolve-issue")], "resolve-issue", BEFORE) is None

    def test_a_slash_command_of_a_longer_name_does_not_count(self):
        entries = [slash_command_load("resolve-issue-extra")]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_files_changed_after_the_load(self):
        entries = [skill_tool_load("resolve-issue")]
        assert staleness(entries, "resolve-issue", BETWEEN) is Staleness.CHANGED

    def test_a_compaction_after_the_load(self):
        entries = [skill_tool_load("resolve-issue"), compaction(T2)]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.COMPACTED

    def test_a_load_after_the_compaction_is_fresh(self):
        entries = [
            skill_tool_load("resolve-issue"),
            compaction(T2),
            skill_tool_load("resolve-issue", T2),
        ]
        assert staleness(entries, "resolve-issue", BETWEEN) is None


def write_transcript(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries) + "not json\n")


def make_skill(skills_root: Path, name: str, mtime: datetime) -> None:
    skill_md = skills_root / name / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("x")
    os.utime(skill_md, (mtime.timestamp(), mtime.timestamp()))


def gh_issue_create(transcript: Path, **fields: str) -> dict[str, Any]:
    return {
        "transcript_path": str(transcript),
        "tool_input": {"command": "gh issue create --title x"},
        **fields,
    }


class TestRefusal:
    def test_allows_a_command_that_is_not_gated(self, tmp_path):
        assert refusal({"tool_input": {"command": "ls"}}, tmp_path) is None

    def test_allows_a_gated_command_after_a_fresh_load(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        assert refusal(gh_issue_create(transcript), tmp_path / "skills") is None

    def test_refuses_a_gated_command_with_no_load(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [])
        assert "file-issue" in (refusal(gh_issue_create(transcript), tmp_path / "skills") or "")

    def test_a_subagent_is_judged_by_its_own_loads_not_its_parents(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        write_transcript(tmp_path / "s" / "subagents" / "agent-a1.jsonl", [])
        payload = gh_issue_create(transcript, agent_id="a1")
        assert refusal(payload, tmp_path / "skills") is not None

    def test_allows_a_subagent_after_its_own_load(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [])
        write_transcript(
            tmp_path / "s" / "subagents" / "agent-a1.jsonl", [skill_tool_load("file-issue")]
        )
        payload = gh_issue_create(transcript, agent_id="a1")
        assert refusal(payload, tmp_path / "skills") is None

    def test_refuses_and_names_the_transcript_when_it_cannot_be_read(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        missing = tmp_path / "missing.jsonl"
        assert str(missing) in (refusal(gh_issue_create(missing), tmp_path / "skills") or "")

    def test_refuses_and_names_the_skill_when_it_cannot_be_found(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        reason = refusal(gh_issue_create(transcript), tmp_path / "skills")
        assert str(tmp_path / "skills" / "file-issue") in (reason or "")

    def test_refuses_when_the_payload_names_no_transcript(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        payload = {"tool_input": {"command": "gh issue create --title x"}}
        assert refusal(payload, tmp_path / "skills") is not None


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False
    )


class TestHookProcess:
    def test_stays_silent_on_a_command_that_is_not_gated(self):
        result = run_hook(json.dumps({"tool_input": {"command": "ls"}}))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_a_gated_command_it_cannot_check(self, tmp_path):
        payload = gh_issue_create(tmp_path / "missing.jsonl")
        output = json.loads(run_hook(json.dumps(payload)).stdout)["hookSpecificOutput"]
        assert (output["hookEventName"], output["permissionDecision"]) == ("PreToolUse", "deny")

    def test_denies_when_its_input_is_not_json(self):
        output = json.loads(run_hook("not json").stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"


class TestHookFileContract:
    def test_source_is_pure_ascii(self):
        assert HOOK.read_bytes().isascii()
