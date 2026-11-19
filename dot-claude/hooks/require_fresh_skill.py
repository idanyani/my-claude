#!/usr/bin/env python3
"""PreToolUse hook: refuse a skill's gated command unless this session's load of the skill is fresh.

A session that loaded a skill hours ago still acts on that text after the skill's files changed,
or after a compaction pushed it out of view. So the commands that carry out a skill's final steps
-- filing an issue, opening and merging a PR -- are refused, with the reason, when the session
never loaded the skill, when the skill's files changed after its last load, or when a compaction
came after that load and Claude Code did not put the skill's text back after it. Loading the
skill again with the Skill tool lets the command through.

The session is the agent the command runs in: a subagent is judged by its own transcript, since
its parent's loads are not in its context. A load is a Skill tool call or a slash command, read
from the transcript `transcript_path` names; the skill's files are those under its directory in
the skills tree this hook is installed beside, Python bytecode excepted, since running the
skill's scripts rewrites it.

It fails closed: a gated command it cannot check is refused, naming what it could not read.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import re
import shlex
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

SKILLS_ROOT = Path(__file__).parent.parent / "skills"

PR_SCRIPTS = frozenset({"open_pr.py", "finish_branch.py"})

# Words that end one shell command and start the next; newlines are kept out of whitespace so
# that each line of a multi-line command is a command of its own.
COMMAND_SEPARATOR_CHARS = "();<>|&\n"
COMMAND_SEPARATORS = frozenset(COMMAND_SEPARATOR_CHARS)

# Words that can stand before the program a command runs: a launcher, its flags, a duration (as
# in `timeout 60`), or a variable assignment.
LAUNCHERS = frozenset({"env", "sudo", "time", "nohup", "exec", "timeout", "uv", "run"})
COMMAND_PREFIX_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*|-.*|\d+[smhd]?")

SHELLS = frozenset({"bash", "sh", "zsh"})

# Global `gh` flags that take a value before the subcommand, as in `gh -R owner/repo issue create`.
GH_FLAGS_WITH_VALUE = frozenset({"-R", "--repo"})


class Staleness(Enum):
    NEVER_LOADED = "this session has not loaded the {skill} skill"
    CHANGED = "the {skill} skill's files changed after this session last loaded it"
    COMPACTED = "a compaction came after this session last loaded the {skill} skill"


def _commands(command: str) -> list[list[str]]:
    """The words of each simple command in a shell command line."""
    try:
        return _lexed_commands(command)
    except ValueError:
        # An unbalanced quote: Bash rejects the line too, but checking it costs only a reload,
        # while letting a gated command through unchecked is what this hook exists to prevent.
        return [
            words
            for part in re.split(f"[{re.escape(COMMAND_SEPARATOR_CHARS)}]", command)
            if (words := part.split())
        ]


def _lexed_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=COMMAND_SEPARATOR_CHARS)
    lexer.whitespace = " \t\r"
    # shlex would also take a `#` inside a word as a comment, and drop the newline after it.
    lexer.commenters = ""
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    for token in lexer:
        if set(token) <= COMMAND_SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [words for words in commands if words]


def _gh_subcommand(args: list[str]) -> list[str]:
    words = []
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
        elif arg in GH_FLAGS_WITH_VALUE:
            skip_value = True
        elif not arg.startswith("-"):
            words.append(arg)
    return words


def _skill_of(words: list[str]) -> str | None:
    while words and (Path(words[0]).name in LAUNCHERS or COMMAND_PREFIX_WORD.fullmatch(words[0])):
        words = words[1:]
    if not words:
        return None
    program, args = Path(words[0]).name, words[1:]
    if program in SHELLS and "-c" in args[:-1]:
        return gated_skill(args[args.index("-c") + 1])
    if program == "gh" and _gh_subcommand(args)[:2] == ["issue", "create"]:
        return "file-issue"
    if program in PR_SCRIPTS or (
        program.startswith("python") and any(Path(arg).name in PR_SCRIPTS for arg in args)
    ):
        return "resolve-issue"
    return None


def gated_skill(command: str) -> str | None:
    """The skill whose final steps `command` carries out, if it runs one of them."""
    return next((skill for words in _commands(command) if (skill := _skill_of(words))), None)


def transcript_of(payload: dict[str, Any]) -> Path:
    """The transcript of the agent the hook fires in.

    In a subagent `transcript_path` still names the main session's transcript; the subagent's
    own lies in a `subagents/` folder beside it, as the SubagentStop hook's `agent_transcript_path`
    shows: https://code.claude.com/docs/en/hooks#subagentstop
    """
    main = Path(payload["transcript_path"])
    agent_id = payload.get("agent_id")
    if not agent_id:
        return main
    return main.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def skill_files_changed_at(skill_dir: Path) -> datetime:
    """When a file of the skill last changed, Python bytecode aside. Raises OSError if none."""
    mtimes = [
        path.stat().st_mtime
        for path in skill_dir.rglob("*")
        if path.is_file() and path.suffix != ".pyc"
    ]
    if not mtimes:
        raise FileNotFoundError(f"{skill_dir}: no files")
    return datetime.fromtimestamp(max(mtimes), timezone.utc)


def _loads(entry: dict[str, Any], skill: str) -> bool:
    content = entry.get("message", {}).get("content")
    if entry.get("type") == "assistant" and isinstance(content, list):
        return any(
            block.get("type") == "tool_use"
            and block.get("name") == "Skill"
            and block.get("input", {}).get("skill") == skill
            for block in content
        )
    if entry.get("type") == "user":
        if isinstance(content, str):
            texts = [content]
        else:
            texts = [
                block.get("text", "") for block in content or [] if block.get("type") == "text"
            ]
        return any(f"<command-name>/{skill}</command-name>" in text for text in texts)
    return False


def _reattaches(entry: dict[str, Any], skill: str) -> bool:
    attachment = entry.get("attachment", {})
    return attachment.get("type") == "invoked_skills" and any(
        invoked.get("name") == skill for invoked in attachment.get("skills", [])
    )


def staleness(
    entries: list[dict[str, Any]], skill: str, files_changed_at: datetime
) -> Staleness | None:
    """Why the session's last load of `skill` is stale, or None if it is fresh."""
    loaded_at = None
    compacted = False
    for entry in entries:
        if _loads(entry, skill):
            loaded_at = datetime.fromisoformat(entry["timestamp"])
            compacted = False
        elif entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            compacted = True
        elif _reattaches(entry, skill):
            # Claude Code puts the text as last loaded back after a compaction; files changed
            # since are still unseen, so the load time stands.
            compacted = False
    if loaded_at is None:
        return Staleness.NEVER_LOADED
    if compacted:
        return Staleness.COMPACTED
    return Staleness.CHANGED if files_changed_at > loaded_at else None


def _read_entries(transcript: Path, skill: str) -> list[dict[str, Any]]:
    """The entries that may load `skill` or compact the session; the rest are not parsed."""
    entries = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        if skill not in line and "compact_boundary" not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def refusal(payload: dict[str, Any], skills_root: Path) -> str | None:
    """Why the command in `payload` is refused, or None to let it run."""
    skill = gated_skill(payload["tool_input"]["command"])
    if skill is None:
        return None
    try:
        entries = _read_entries(transcript_of(payload), skill)
        files_changed_at = skill_files_changed_at(skills_root / skill)
    except Exception as error:  # noqa: BLE001 -- any failure to read means it cannot check
        return f"Cannot check that the {skill} skill is fresh: cannot read {error}."
    stale = staleness(entries, skill, files_changed_at)
    if stale is None:
        return None
    return (
        f"Refused: {stale.value.format(skill=skill)}. This command carries out a step "
        f"of that skill, so act on its current text: load it again with the Skill tool "
        f"(skill: {skill}), follow its steps from where the work stands, then rerun the command."
    )


def main(argv: list[str]) -> int:
    try:
        reason = refusal(json.load(sys.stdin), SKILLS_ROOT)
    except Exception as error:  # noqa: BLE001 -- an uncaught error would let the command run
        reason = f"Cannot check the command against the skills it may need: {error!r}."
    if reason is not None:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
