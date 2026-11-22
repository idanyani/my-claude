"""Tests for the hook that refuses a skill's gated command unless the session's load of it is fresh.

Transcript entries are built in each test with only the fields the hook reads.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from hook_process import run_hook
from require_fresh_skill import (
    Staleness,
    gated_skill,
    refusal,
    skill_files_changed_at,
    staleness,
    transcript_of,
)

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / "dot-claude" / "hooks" / "require_fresh_skill.py"

LOADED_AT = "2026-11-17T18:16:00.000Z"
LATER = "2026-11-17T20:15:00.000Z"
BETWEEN = datetime(2026, 11, 17, 19, 0, tzinfo=UTC)
BEFORE = datetime(2026, 11, 17, 18, 0, tzinfo=UTC)
AT_LOAD = datetime(2026, 11, 17, 18, 16, tzinfo=UTC)


def skill_tool_load(skill: str, timestamp: str = LOADED_AT) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]},
    }


def slash_command_load(skill: str, timestamp: str = LOADED_AT) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {"content": f"<command-name>/{skill}</command-name>"},
    }


def compaction(timestamp: str) -> dict[str, Any]:
    return {"type": "system", "subtype": "compact_boundary", "timestamp": timestamp}


def reattachment(*skills: str) -> dict[str, Any]:
    """The entry that puts the session's invoked skills back in context after a compaction."""
    return {
        "type": "attachment",
        "attachment": {"type": "invoked_skills", "skills": [{"name": s} for s in skills]},
    }


class TestGatedSkill:
    @pytest.mark.parametrize(
        "command",
        [
            "python3 /home/u/.claude/skills/resolve-issue/scripts/open_pr.py --footer x",
            "python3 /home/u/.claude/skills/resolve-issue/scripts/finish_branch.py 12",
            "git switch 7-x && python /s/scripts/finish_branch.py 7",
            "/usr/bin/python3 /s/scripts/open_pr.py --no-footer",
            "python3 -u /s/scripts/open_pr.py --no-footer",
            "python3 -X dev /s/scripts/open_pr.py --no-footer",
            "/s/scripts/finish_branch.py 7",
            "uv run /s/scripts/open_pr.py --no-footer",
            "uv run python /s/scripts/open_pr.py --no-footer",
        ],
    )
    def test_the_pr_scripts_need_resolve_issue(self, command):
        assert gated_skill(command) == "resolve-issue"

    @pytest.mark.parametrize(
        "command",
        [
            "python3 /home/u/.claude/skills/file-issue/scripts/file_issue.py --origin agent",
            "/s/scripts/file_issue.py --origin agent",
        ],
    )
    def test_the_filing_script_needs_file_issue(self, command):
        assert gated_skill(command) == "file-issue"

    @pytest.mark.parametrize(
        "command",
        [
            "gh issue list --state open",
            "gh issue create --title x",
            "gh pr merge 5 --squash",
            "gh issue view 3",
            'grep -n "gh issue create" README.md',
            "uv run pytest tests/test_open_pr.py",
            "git add dot-claude/skills/resolve-issue/scripts/finish_branch.py",
            'git commit -m "Run finish_branch.py after open_pr.py"',
            "python3 dot-claude/skills/resolve-issue/scripts/start_branch.py 7 x",
            "echo 'unterminated",
            "git issue create",
            "cat dot-claude/skills/resolve-issue/scripts/open_pr.py",
            "python3 tests/test_open_pr.py",
            "ls;",
            "ls\n",
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
        assert skill_files_changed_at(tmp_path) == datetime(1970, 1, 1, 0, 33, 20, tzinfo=UTC)

    def test_ignores_bytecode_running_the_scripts_writes(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("x")
        os.utime(tmp_path / "SKILL.md", (1000, 1000))
        cache = tmp_path / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "run.cpython-312.pyc").write_text("x")
        (tmp_path / "scripts" / "stray.pyc").write_text("x")
        assert skill_files_changed_at(tmp_path) == datetime(1970, 1, 1, 0, 16, 40, tzinfo=UTC)

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

    def test_a_slash_command_in_a_text_block_counts(self):
        entry = slash_command_load("resolve-issue")
        text = entry["message"]["content"]
        entry["message"]["content"] = [{"type": "image"}, {"type": "text", "text": text}]
        assert staleness([entry], "resolve-issue", BEFORE) is None

    def test_the_assistant_quoting_a_slash_command_is_not_a_load(self):
        text = slash_command_load("resolve-issue")["message"]["content"]
        entry = {
            "type": "assistant",
            "timestamp": LOADED_AT,
            "message": {"content": [{"type": "text", "text": text}]},
        }
        assert staleness([entry], "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_another_tool_naming_the_skill_is_not_a_load(self):
        entry = skill_tool_load("resolve-issue")
        entry["message"]["content"][0]["name"] = "Agent"
        assert staleness([entry], "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_files_changed_at_the_moment_of_the_load_are_fresh(self):
        entries = [skill_tool_load("resolve-issue")]
        assert staleness(entries, "resolve-issue", AT_LOAD) is None

    def test_a_system_entry_other_than_a_compaction_keeps_the_load_fresh(self):
        entries = [skill_tool_load("resolve-issue"), {"type": "system", "subtype": "other"}]
        assert staleness(entries, "resolve-issue", BEFORE) is None

    def test_a_slash_command_of_a_longer_name_does_not_count(self):
        entries = [slash_command_load("resolve-issue-extra")]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.NEVER_LOADED

    def test_files_changed_after_the_load(self):
        entries = [skill_tool_load("resolve-issue")]
        assert staleness(entries, "resolve-issue", BETWEEN) is Staleness.CHANGED

    def test_a_compaction_after_the_load(self):
        entries = [skill_tool_load("resolve-issue"), compaction(LATER)]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.COMPACTED

    def test_a_reattachment_after_the_compaction_keeps_the_load_fresh(self):
        entries = [
            skill_tool_load("resolve-issue"),
            compaction(LATER),
            reattachment("brief", "resolve-issue"),
        ]
        assert staleness(entries, "resolve-issue", BEFORE) is None

    def test_a_reattachment_of_other_skills_leaves_the_compaction(self):
        entries = [skill_tool_load("resolve-issue"), compaction(LATER), reattachment("brief")]
        assert staleness(entries, "resolve-issue", BEFORE) is Staleness.COMPACTED

    def test_a_reattachment_is_not_a_fresh_load(self):
        # It carries the text as last loaded, so files changed since are still unseen.
        entries = [
            skill_tool_load("resolve-issue"),
            compaction(LATER),
            reattachment("resolve-issue"),
        ]
        assert staleness(entries, "resolve-issue", BETWEEN) is Staleness.CHANGED

    def test_a_load_after_the_compaction_is_fresh(self):
        entries = [
            skill_tool_load("resolve-issue"),
            compaction(LATER),
            skill_tool_load("resolve-issue", LATER),
        ]
        assert staleness(entries, "resolve-issue", BETWEEN) is None


def write_transcript(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))


def make_skill(skills_root: Path, name: str, mtime: datetime) -> None:
    skill_md = skills_root / name / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("x")
    os.utime(skill_md, (mtime.timestamp(), mtime.timestamp()))


FILE_ISSUE_RUN = "python3 /s/scripts/file_issue.py --origin agent --title x"


def file_issue_run(transcript: Path, **fields: str) -> dict[str, Any]:
    return {
        "transcript_path": str(transcript),
        "tool_input": {"command": FILE_ISSUE_RUN},
        **fields,
    }


class TestRefusal:
    def test_allows_a_command_that_is_not_gated(self, tmp_path):
        assert refusal({"tool_input": {"command": "ls"}}, tmp_path) is None

    def test_allows_a_gated_command_after_a_fresh_load(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        assert refusal(file_issue_run(transcript), tmp_path / "skills") is None

    @pytest.mark.parametrize(
        ("entries", "files_changed_at"),
        [
            ([], BEFORE),
            ([skill_tool_load("file-issue")], BETWEEN),
            ([skill_tool_load("file-issue"), compaction(LATER)], BEFORE),
            (
                [{"type": "assistant", "message": slash_command_load("file-issue")["message"]}],
                BEFORE,
            ),
        ],
        ids=["never-loaded", "changed", "compacted", "load-without-timestamp"],
    )
    def test_refuses_a_gated_command_without_a_fresh_load(
        self, tmp_path, entries, files_changed_at
    ):
        make_skill(tmp_path / "skills", "file-issue", files_changed_at)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, entries)
        assert refusal(file_issue_run(transcript), tmp_path / "skills") is not None

    def test_refuses_a_pr_script_until_resolve_issue_is_loaded(self, tmp_path):
        make_skill(tmp_path / "skills", "resolve-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        payload = {
            "transcript_path": str(transcript),
            "tool_input": {"command": "python3 /s/scripts/finish_branch.py 7"},
        }
        assert refusal(payload, tmp_path / "skills") is not None
        write_transcript(transcript, [skill_tool_load("resolve-issue")])
        assert refusal(payload, tmp_path / "skills") is None

    def test_skips_lines_that_are_not_json_objects(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        load = json.dumps(skill_tool_load("file-issue"))
        transcript.write_text(f'{{"skill": "file-issue"\n"file-issue"\n{load}\n')
        assert refusal(file_issue_run(transcript), tmp_path / "skills") is None

    def test_a_subagent_is_judged_by_its_own_loads_not_its_parents(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        write_transcript(tmp_path / "s" / "subagents" / "agent-a1.jsonl", [])
        payload = file_issue_run(transcript, agent_id="a1")
        assert refusal(payload, tmp_path / "skills") is not None

    def test_allows_a_subagent_after_its_own_load(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [])
        write_transcript(
            tmp_path / "s" / "subagents" / "agent-a1.jsonl", [skill_tool_load("file-issue")]
        )
        payload = file_issue_run(transcript, agent_id="a1")
        assert refusal(payload, tmp_path / "skills") is None

    def test_refuses_and_names_the_transcript_when_it_cannot_be_read(self, tmp_path):
        make_skill(tmp_path / "skills", "file-issue", BEFORE)
        missing = tmp_path / "missing.jsonl"
        assert str(missing) in (refusal(file_issue_run(missing), tmp_path / "skills") or "")

    def test_refuses_and_names_the_skill_when_it_cannot_be_found(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue")])
        reason = refusal(file_issue_run(transcript), tmp_path / "skills")
        assert str(tmp_path / "skills" / "file-issue") in (reason or "")

    def test_refuses_when_the_payload_names_no_transcript(self, tmp_path):
        payload = {"tool_input": {"command": FILE_ISSUE_RUN}}
        assert refusal(payload, tmp_path / "skills") is not None


class TestHookProcess:
    def test_stays_silent_on_a_command_that_is_not_gated(self):
        result = run_hook(HOOK, json.dumps({"tool_input": {"command": "ls"}}))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_a_gated_command_it_cannot_check_and_says_why(self, tmp_path):
        missing = tmp_path / "missing.jsonl"
        output = json.loads(run_hook(HOOK, json.dumps(file_issue_run(missing))).stdout)
        decision = output["hookSpecificOutput"]
        assert (decision["hookEventName"], decision["permissionDecision"]) == ("PreToolUse", "deny")
        assert str(missing) in decision["permissionDecisionReason"]

    def test_allows_a_gated_command_after_a_load_of_the_installed_skill(self, tmp_path):
        # A load dated after every file of the repo's own file-issue skill.
        transcript = tmp_path / "s.jsonl"
        write_transcript(transcript, [skill_tool_load("file-issue", "2100-01-01T00:00:00.000Z")])
        result = run_hook(HOOK, json.dumps(file_issue_run(transcript)))
        assert (result.returncode, result.stdout) == (0, "")

    def test_denies_when_its_input_is_not_json(self):
        output = json.loads(run_hook(HOOK, "not json").stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"


class TestHookFileContract:
    def test_source_is_pure_ascii(self):
        assert HOOK.read_bytes().isascii()
