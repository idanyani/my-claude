#!/usr/bin/env python3
"""PreToolUse hook: deny `pgrep -f` / `pkill -f` patterns that match the calling shell itself.

`-f` matches a pattern against each process's whole command line, and the shell running the
`pgrep` has that very pattern in its own argv. So an unescaped pattern always finds at least the
caller, and `until ! pgrep -f "<pattern>"; do sleep; done` waits for itself rather than for the
job -- a loop that can never exit. The standard fix is a one-character regex bracket:
`[p]ytest` matches a real `pytest` command line but not the literal text `[p]ytest`.

The defect is provable from the command text alone, which is what makes this a hook rather than
a judgment call for the `maintain` skill, and what makes denying rather than advising fair: the
fix is mechanical. Deny is also right outside a loop, where the same self-match silently returns
a bogus PID.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import re
import shlex
import sys
from dataclasses import dataclass

PROCESS_MATCHERS = frozenset({"pgrep", "pkill"})

# Tokens that end one command and begin the next, bounding a single pgrep/pkill invocation.
COMMAND_SEPARATORS = frozenset({"&&", "||", "|", ";", "&", "(", ")", "\n"})

# A redirection ends the argument list: neither the operator nor its target is a pgrep operand.
# Only bare operators match, so a quoted pattern containing `>` is still read as the pattern.
REDIRECTION = re.compile(r"^\d*(?:>>?|<<?|[<>]&)-?$")

# A heredoc body is data the command reads on stdin, never anything the shell runs -- writing
# about this bug must not trip the check. Everything from the delimiter to its closing line is
# dropped before the scan.
HEREDOC_START = re.compile(r"""<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1""")

# Short options that consume the following token, so its value is never mistaken for the pattern.
SHORT_OPTIONS_WITH_VALUE = frozenset("dgGPstuUFjrqMN")
LONG_OPTIONS_WITH_VALUE = frozenset(
    {
        "--delimiter",
        "--group",
        "--pgroup",
        "--parent",
        "--session",
        "--terminal",
        "--euid",
        "--uid",
        "--pidfile",
        "--jail",
        "--signal",
        "--ns",
        "--nslist",
        "--runstates",
        "--queue",
        "--cgroup",
        "--core",
        "--namespace",
    }
)

# A bracket expression anywhere in the pattern breaks the self-match: the literal text `[p]ytest`
# does not satisfy the regex `[p]ytest`, while a real `pytest` command line does.
BRACKET_EXPRESSION = re.compile(r"\[[^]]+]")

# Shell expansions make the pattern differ from the literal text in the caller's argv, so a
# self-match is no longer provable from the command alone.
DYNAMIC_MARKERS = ("$", "`")


@dataclass(frozen=True)
class SelfMatch:
    pattern: str
    suggestion: str


def bracket_escape(pattern: str) -> str:
    """`pattern` with its first alphanumeric character wrapped in a regex bracket expression."""
    for index, char in enumerate(pattern):
        if char.isalnum():
            return f"{pattern[:index]}[{char}]{pattern[index + 1 :]}"
    return pattern


def _tokenize(command: str) -> list[str]:
    """Shell tokens of `command`, with operators split off from adjacent quoted words."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _without_heredocs(command: str) -> str:
    """`command` with every heredoc body and its closing delimiter removed.

    Stripping the bodies as text rather than as tokens keeps their contents away from the
    lexer entirely, so an apostrophe in prose cannot make the whole command unparsable.
    """
    lines = command.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        kept.append(lines[index])
        delimiters = [delimiter for _, delimiter in HEREDOC_START.findall(lines[index])]
        index += 1
        for delimiter in delimiters:
            while index < len(lines) and lines[index].strip() != delimiter:
                index += 1
            index += 1
    return "\n".join(kept)


def _pattern_of_invocation(tokens: list[str], start: int) -> tuple[str | None, int]:
    """The `-f` pattern of the pgrep/pkill invocation at `start`, and the index just past it.

    Returns `None` for the pattern when the invocation does not use `-f`, in which case pgrep
    matches process names only and cannot see the caller's command line.
    """
    index = start + 1
    matches_full_command_line = False
    operands: list[str] = []
    while index < len(tokens) and tokens[index] not in COMMAND_SEPARATORS:
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if REDIRECTION.match(token) or (
            token.isdigit() and operands and REDIRECTION.match(following)
        ):
            # A redirection, or the file descriptor introducing one.
            break
        if token == "--":
            index += 1
            while index < len(tokens) and tokens[index] not in COMMAND_SEPARATORS:
                operands.append(tokens[index])
                index += 1
            break
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            matches_full_command_line |= name == "--full"
            if name in LONG_OPTIONS_WITH_VALUE and "=" not in token:
                index += 1
        elif token.startswith("-") and len(token) > 1:
            cluster = token[1:]
            matches_full_command_line |= "f" in cluster
            if cluster[-1] in SHORT_OPTIONS_WITH_VALUE:
                index += 1
        else:
            operands.append(token)
        index += 1
    if not matches_full_command_line or not operands:
        return None, index
    return operands[-1], index


def _matches_in_line(tokens: list[str]) -> list[SelfMatch]:
    """Every self-matching pattern among one line's tokens."""
    matches = []
    index = 0
    while index < len(tokens):
        if tokens[index].rsplit("/", 1)[-1] not in PROCESS_MATCHERS:
            index += 1
            continue
        pattern, index = _pattern_of_invocation(tokens, index)
        if pattern is None:
            continue
        if any(marker in pattern for marker in DYNAMIC_MARKERS):
            continue
        if BRACKET_EXPRESSION.search(pattern):
            continue
        matches.append(SelfMatch(pattern, bracket_escape(pattern)))
    return matches


def find_self_matches(command: str) -> list[SelfMatch]:
    """Every `pgrep -f`/`pkill -f` pattern in `command` that provably matches the caller itself.

    Each line is scanned on its own: `shlex` treats a newline as plain whitespace, so a single
    token stream would let one invocation collect operands from the command on the next line.
    """
    matches = []
    for line in _without_heredocs(command).split("\n"):
        try:
            tokens = _tokenize(line)
        except ValueError:
            # Unbalanced quoting on this line; the shell rejects it before matching anything.
            continue
        matches.extend(_matches_in_line(tokens))
    return matches


def format_denial(matches: list[SelfMatch]) -> str:
    """Denial reason naming each self-matching pattern and the bracketed form that fixes it."""
    lines = [
        "`-f` matches whole command lines, so this pattern matches the shell running it. "
        "A wait loop built on it can never exit. Bracket one character:"
    ]
    lines.extend(f"  {match.pattern!r} -- use {match.suggestion!r}" for match in matches)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command")
    if not command:
        return 0
    matches = find_self_matches(command)
    if matches:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": format_denial(matches),
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level hook guard: never break the tool flow
        print(error, file=sys.stderr)
        sys.exit(0)
