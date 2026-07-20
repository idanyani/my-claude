#!/usr/bin/env python3
"""PostToolUse hook: flag the CLAUDE.md prose-convention violations a language linter misses.

The global conventions require ASCII typography in code and text files (`--`/`---` not em/en-dashes,
`->` not Unicode arrows) and reserve emojis for user-facing scripts. Language linters (ruff, mypy,
eslint) never check this, and it is deterministic, so it belongs in a hook rather than the
judgment-based `maintain` skill. This runs after every Edit/Write, reads the hook payload on stdin,
scans the edited file, and returns advisory (non-blocking) feedback naming each offending line and
its ASCII replacement.

Stdlib-only: it needs just `python3`, so it runs in any repo the config is installed into.
"""

import json
import sys
from dataclasses import dataclass

# Typographic codepoints the conventions forbid, mapped to the ASCII the author almost certainly
# meant. Hebrew and other legitimate non-ASCII content is intentionally not flagged -- only these
# punctuation substitutions, near-always an editor auto-correct slip. Keyed by codepoint so this
# table itself stays pure ASCII; the hook would otherwise flag its own source.
GLYPH_REPLACEMENTS = {
    0x2014: "--",  # em dash
    0x2013: "-",  # en dash
    0x2018: "'",  # left single quotation mark
    0x2019: "'",  # right single quotation mark / typographic apostrophe
    0x201C: '"',  # left double quotation mark
    0x201D: '"',  # right double quotation mark
    0x2026: "...",  # horizontal ellipsis
    0x2192: "->",  # rightwards arrow
    0x2190: "<-",  # leftwards arrow
    0x2194: "<->",  # left right arrow
    0x00A0: " ",  # no-break space
}

# Unicode blocks that are emoji/pictographs. Advisory only: the hook cannot tell a user-facing
# script (where emojis are allowed) from code or docs (where they are not), so it never blocks.
EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # symbols, pictographs, emoticons, transport, supplemental
    (0x2600, 0x27BF),  # miscellaneous symbols and dingbats
    (0x1F000, 0x1F0FF),  # mahjong/domino/playing cards
    (0xFE00, 0xFE0F),  # variation selectors (emoji presentation)
)


@dataclass(frozen=True)
class Violation:
    line: int  # 1-indexed
    column: int  # 1-indexed
    char: str
    replacement: str | None  # ASCII suggestion, or None for emoji (context-dependent)


def is_emoji(char: str) -> bool:
    """Whether a single character falls in a pictographic/emoji Unicode block."""
    codepoint = ord(char)
    return any(low <= codepoint <= high for low, high in EMOJI_RANGES)


def find_violations(text: str) -> list[Violation]:
    """All prose-convention violations in `text`, in reading order."""
    violations = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for column, char in enumerate(line, start=1):
            replacement = GLYPH_REPLACEMENTS.get(ord(char))
            if replacement is not None:
                violations.append(Violation(line_number, column, char, replacement))
            elif is_emoji(char):
                violations.append(Violation(line_number, column, char, None))
    return violations


def format_report(file_path: str, violations: list[Violation]) -> str:
    """Advisory message listing each violation as `file:line:col`, for the hook's context feedback."""
    header = (
        f"Prose-convention issues in {file_path} "
        "(CLAUDE.md: ASCII typography, no emoji in code/docs):"
    )
    lines = [header]
    for violation in violations:
        location = f"{file_path}:{violation.line}:{violation.column}"
        codepoint = f"U+{ord(violation.char):04X}"
        if violation.replacement is not None:
            lines.append(f"  {location}: {codepoint} -- use `{violation.replacement}`")
        else:
            lines.append(
                f"  {location}: emoji {codepoint} -- remove unless this is a user-facing script"
            )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0
    try:
        with open(file_path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        # Unreadable or binary: nothing this hook can say about it.
        return 0
    violations = find_violations(text)
    if violations:
        context = format_report(file_path, violations)
        json.dump(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}},
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 -- top-level hook guard: never break the edit flow
        print(error, file=sys.stderr)
        sys.exit(0)
