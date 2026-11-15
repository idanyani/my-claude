#!/usr/bin/env python3
"""PreToolUse hook: deny `pgrep -f` / `pkill -f` patterns that match the calling shell itself.

`-f` matches a pattern against each process's whole command line, and the shell running the
`pgrep` has that very pattern in its own argv. So an unescaped pattern always finds at least the
caller, and `until ! pgrep -f "<pattern>"; do sleep; done` waits for itself rather than for the
job -- a loop that can never exit. The standard fix is a one-character regex bracket:
`[p]ytest` matches a real `pytest` command line but not the literal text `[p]ytest`.

The defect is provable from the command text alone, which is what makes this a hook rather than
a judgment call left to review, and what makes denying rather than advising fair: the
fix is mechanical. Deny is also right outside a loop, where the same self-match silently returns
a bogus PID.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import re
import shlex
import sys
from collections.abc import Iterator
from dataclasses import dataclass

PROCESS_MATCHERS = frozenset({"pgrep", "pkill"})

# Tokens that end one command and begin the next, bounding a single pgrep/pkill invocation.
COMMAND_SEPARATORS = frozenset({"&&", "||", "|", ";", "&", "(", ")"})

# A redirection ends the argument list: neither the operator nor its target is a pgrep operand.
# Only bare operators match, so a quoted pattern containing `>` is still read as the pattern.
REDIRECTION = re.compile(r"^\d*(?:>>?|<<?|[<>]&)-?$")

QUOTES = frozenset("'\"")

# Unquoted characters that end a shell word.
METACHARACTERS = frozenset(" \t;&|()<>")

# Markers on the stack of open quoting contexts, beside the quote characters themselves.
ANSI_C_QUOTE = "$'"
SUBSHELL = "$("  # a command substitution or a plain `(` subshell
ARITHMETIC = "(("  # `$((...))` or `((...))`, where `<<` is a shift
BACKTICK = "`"
CASE = "case"  # a `case` command, whose pattern lists end in an unquoted `)`

# The reserved words that open and close a `case` command, as whole unquoted words. Bash
# reserves them only where a command starts, which `_at_command_start` decides.
CASE_KEYWORD = re.compile(r"(?<![^ \t;&|()<>`])(case|esac)(?=[ \t;&|()<>`]|$)")

# Reserved words after which the next word still starts a command, as in `then case ...`.
COMMAND_PREFIX_WORDS = frozenset({"!", "{", "if", "then", "else", "elif", "while", "until", "do"})
LAST_WORD = re.compile(r"[^ \t;&|()<>`]+$")

# Contexts in which a newline is part of a word rather than a command separator.
QUOTING_CONTEXTS = QUOTES | {ANSI_C_QUOTE}

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

# What `shlex` raises when the text ends right after a backslash: outside single quotes, that
# backslash escapes the newline that follows it in the command -- a line continuation. The
# message is the only signal the public API gives; the lexer's state is undocumented.
DANGLING_ESCAPE = "No escaped character"

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


@dataclass(frozen=True)
class HeredocDelimiter:
    word: str
    strips_tabs: bool  # `<<-` strips leading tabs from body lines, the closing one included

    def closes(self, line: str) -> bool:
        return (line.lstrip("\t") if self.strips_tabs else line) == self.word


def _heredoc_delimiter(line: str, index: int) -> tuple[HeredocDelimiter, int]:
    """The delimiter of the heredoc whose `<<` ends just before `index`, and the index past it.

    The delimiter is the next shell word after quote removal: `<<'EOF'` and `<<"EOF"` both end
    at a line reading `EOF`.
    """
    strips_tabs = line.startswith("-", index)
    index += strips_tabs
    while index < len(line) and line[index] in " \t":
        index += 1
    word = []
    quote = None
    while index < len(line):
        char = line[index]
        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in QUOTES:
            quote = char
        elif char == "\\":
            index += 1
            word.append(line[index : index + 1])
        elif char in METACHARACTERS or char == BACKTICK:  # a backtick may close a substitution
            break
        else:
            word.append(char)
        index += 1
    return HeredocDelimiter("".join(word), strips_tabs), index


def _at_command_start(line: str, index: int) -> bool:
    """Whether a word at `index` of `line` is the first word of a command.

    It is when only blanks separate it from the start of the line, a control operator, a
    parenthesis, a backtick, or a reserved word that leaves the command unstarted. A physical
    line start counts, even after a backslash-newline that continues the command before it.
    """
    before = line[:index].rstrip(" \t")
    if not before or before[-1] in ";&|()`":
        return True
    last_word = LAST_WORD.search(before)
    return last_word is not None and last_word.group() in COMMAND_PREFIX_WORDS


def _scan_quoting(line: str, contexts: list[str]) -> tuple[list[HeredocDelimiter], bool]:
    """Advance the open quoting `contexts` across `line`; return the heredocs it opens.

    Also returns whether `line` ends in a backslash that escapes its newline. `contexts` is a
    stack of open quotes and substitutions: `$(` and a backtick start a fresh unquoted context
    even inside double quotes, which is how the `"$(cat <<'EOF' ...)"` idiom opens a real
    heredoc.
    """
    delimiters: list[HeredocDelimiter] = []
    # Bash reads a backtick substitution to its closing backtick before parsing it, so a
    # heredoc opened inside one ends there.
    backtick_starts: list[int] = []
    index = 0
    while index < len(line):
        char = line[index]
        top = contexts[-1] if contexts else None
        if top == "'":
            if char == "'":
                contexts.pop()
        elif top == ANSI_C_QUOTE:
            if char == "\\":
                index += 1
            elif char == "'":
                contexts.pop()
        elif char == "\\":
            if index == len(line) - 1:
                return delimiters, True
            index += 1
        elif char == BACKTICK:
            if top == BACKTICK:
                contexts.pop()
                if backtick_starts:
                    del delimiters[backtick_starts.pop() :]
            else:
                contexts.append(BACKTICK)
                backtick_starts.append(len(delimiters))
        elif line.startswith("$((", index):
            contexts.append(ARITHMETIC)
            index += 2
        elif line.startswith("$(", index):
            contexts.append(SUBSHELL)
            index += 1
        elif top == '"':
            if char == '"':
                contexts.pop()
        elif line.startswith(ANSI_C_QUOTE, index):
            contexts.append(ANSI_C_QUOTE)
            index += 1
        elif char in QUOTES:
            contexts.append(char)
        elif line.startswith("((", index):
            contexts.append(ARITHMETIC)
            index += 1
        elif char == "(":
            contexts.append(SUBSHELL)
        elif char == ")":
            if top == ARITHMETIC and line.startswith("))", index):
                contexts.pop()
                index += 1
            elif top == SUBSHELL:
                contexts.pop()
        elif char == "#" and (index == 0 or line[index - 1] in METACHARACTERS):
            break  # a comment: its apostrophes quote nothing
        elif (keyword := CASE_KEYWORD.match(line, index)) and _at_command_start(line, index):
            if keyword.group() == "case":
                contexts.append(CASE)
            elif top == CASE:
                contexts.pop()
            index = keyword.end()
            continue
        elif ARITHMETIC in contexts:
            pass  # `<<` is a shift
        elif line.startswith("<<<", index):
            index += 2  # a here-string, whose operand is an ordinary word
        elif line.startswith("<<", index):
            delimiter, index = _heredoc_delimiter(line, index + 2)
            if delimiter.word:  # bash rejects an empty one, so there is no body to skip
                delimiters.append(delimiter)
            continue
        index += 1
    return delimiters, False


def _heredoc_free_lines(
    lines: list[str], tracks_quoting_across_lines: bool
) -> tuple[list[str], bool]:
    """`lines` without heredoc bodies, and whether every quoting context closed by the end."""
    kept = []
    contexts: list[str] = []
    pending: list[HeredocDelimiter] = []
    index = 0
    while index < len(lines):
        if not tracks_quoting_across_lines:
            contexts.clear()
        delimiters, newline_is_escaped = _scan_quoting(lines[index], contexts)
        pending.extend(delimiters)
        kept.append(lines[index])
        index += 1
        newline_is_quoted = (
            tracks_quoting_across_lines and bool(contexts) and contexts[-1] in QUOTING_CONTEXTS
        )
        if newline_is_escaped or newline_is_quoted:
            continue  # the body starts only after a newline the shell reads as a separator
        for delimiter in pending:
            while index < len(lines) and not delimiter.closes(lines[index]):
                index += 1
            index += 1
        pending = []
    return kept, not contexts


def _without_heredocs(command: str) -> str:
    """`command` with every heredoc body and its closing delimiter removed.

    A heredoc body is data the command reads on stdin, never anything the shell runs -- writing
    about this bug must not trip the check. Only an unquoted `<<` opens one, so the scan tracks
    quoting. Stripping the bodies as text rather than as tokens keeps their contents away from
    the lexer entirely, so an apostrophe in prose cannot make the whole command unparsable.

    Quoting left open at the end is either invalid bash or a construct the scan misreads, and
    one misread would otherwise hide every later heredoc. Then each line is scanned on its own,
    which confines a misread to its line.
    """
    lines = command.split("\n")
    kept, balanced = _heredoc_free_lines(lines, tracks_quoting_across_lines=True)
    if not balanced:
        kept, _ = _heredoc_free_lines(lines, tracks_quoting_across_lines=False)
    return "\n".join(kept)


def _open_quote(text: str) -> str:
    """The quote character left open at the end of `text`, which lexes only with a quote open."""
    try:
        _tokenize(text + '"')
    except ValueError:
        return "'"
    return '"'


def _command_lines(command: str) -> Iterator[list[str]]:
    """Tokens of each line of `command` as the shell reads it, joining physical lines.

    A newline ends a command only when it is unquoted and unescaped. A backslash-newline outside
    single quotes is a line continuation, which the shell removes before splitting words; a
    newline inside open quotes belongs to the quoted word.
    """
    lines = command.split("\n")
    pending = ""
    open_quote = None
    first_pending_line = 0
    for index, line in enumerate(lines):
        if not pending:
            first_pending_line = index
        text = pending + line
        if open_quote and open_quote not in line and not line.endswith("\\"):
            # Nothing on this line can close the quote, so lexing again would only repeat the
            # failure -- and cost time quadratic in the length of a long quoted argument.
            pending = text + "\n"
            continue
        try:
            tokens = _tokenize(text)
        except ValueError as error:
            if str(error) == DANGLING_ESCAPE:
                pending, open_quote = text[:-1], None
            else:
                pending, open_quote = text + "\n", _open_quote(text)
            continue
        pending, open_quote = "", None
        yield tokens
    # A quote shlex never saw closed may still be valid bash, such as ANSI-C `$'it\\'s'`; scan
    # those lines one by one so it hides no later command.
    for line in lines[first_pending_line:] if pending else []:
        try:
            yield _tokenize(line)
        except ValueError:
            continue


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
    """Every self-matching pattern among one command line's tokens."""
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

    Each command line is scanned on its own: `shlex` treats a newline as plain whitespace, so a
    single token stream would let one invocation collect operands from the command on the next
    line.
    """
    matches = []
    for tokens in _command_lines(_without_heredocs(command)):
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
