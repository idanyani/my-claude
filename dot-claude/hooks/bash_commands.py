"""Shared by the PreToolUse hooks that gate Bash commands: split a command line into the simple
commands it runs, and answer Claude Code for a tool call.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import re
import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Words that end one shell command and start the next, a backtick substitution's included;
# newlines are kept out of whitespace so that each line of a multi-line command is a command of
# its own.
COMMAND_SEPARATOR_CHARS = "();<>|&`\n"
COMMAND_SEPARATORS = frozenset(COMMAND_SEPARATOR_CHARS)

# Words that can stand before the program a command runs: a launcher, its flags, a duration (as
# in `timeout 60`), or a variable assignment.
LAUNCHERS = frozenset(
    {"env", "sudo", "time", "nohup", "exec", "timeout", "uv", "run", "command", "xargs"}
)
COMMAND_PREFIX_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*|-.*|\d+[smhd]?")

SHELLS = frozenset({"bash", "sh", "zsh"})

# Global `gh` flags that take a value before the subcommand, as in `gh -R owner/repo issue create`.
GH_FLAGS_WITH_VALUE = frozenset({"-R", "--repo"})


def _split(command: str) -> list[list[str]]:
    try:
        return _lexed(command)
    except ValueError:
        # An unbalanced quote: Bash rejects the line too, but checking it costs the caller only a
        # retry, while letting a gated command through unchecked is what the hooks exist to prevent.
        return [
            words
            for part in re.split(f"[{re.escape(COMMAND_SEPARATOR_CHARS)}]", command)
            if (words := part.split())
        ]


def _lexed(command: str) -> list[list[str]]:
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


def simple_commands(command: str) -> list[list[str]]:
    """The words of each simple command a command line runs, from its program on.

    Launchers and variable assignments before the program are dropped, its name is reduced to the
    file name (`/usr/bin/gh` --> `gh`), and a shell's `-c` script is split into its own commands.
    A launcher flag's value (`sudo -u bob`) cannot be told from a program, so a shell is looked for
    anywhere in a command's words, and callers look for the program they gate the same way.
    """
    commands = []
    for words in _split(command):
        while words and (
            Path(words[0]).name in LAUNCHERS or COMMAND_PREFIX_WORD.fullmatch(words[0])
        ):
            words = words[1:]
        if not words:
            continue
        words = [Path(words[0]).name, *words[1:]]
        shell = next(
            (
                i
                for i, word in enumerate(words)
                if Path(word).name in SHELLS and "-c" in words[i + 1 : -1]
            ),
            None,
        )
        if shell is None:
            commands.append(words)
        else:
            commands.extend(simple_commands(words[words.index("-c", shell + 1) + 1]))
    return commands


def _gh_subcommand(args: list[str]) -> list[str]:
    """The words of a `gh` command that are neither flags nor the values of its global flags."""
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


def gh_issue_create_args(words: list[str]) -> list[str] | None:
    """The words after `gh` when a simple command runs `gh issue create`, else None."""
    for i, word in enumerate(words):
        if Path(word).name == "gh" and _gh_subcommand(words[i + 1 :])[:2] == ["issue", "create"]:
            return words[i + 1 :]
    return None


def run_gate(refusal: Callable[[dict[str, Any]], str | None], cannot_check: str) -> int:
    """Answer Claude Code for one tool call: deny it when `refusal` of its payload gives a reason.

    It fails closed: an error reading the payload or checking it denies the call too, naming
    `cannot_check` and the error, since a hook that crashed would let the command run.
    """
    try:
        reason = refusal(json.load(sys.stdin))
    except Exception as error:  # noqa: BLE001 -- an uncaught error would let the command run
        reason = f"{cannot_check}: {error!r}."
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
