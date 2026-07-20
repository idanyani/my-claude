"""Tests for the prose-convention hook.

Inputs are built with `chr()` so this test file itself stays pure ASCII -- the same reason the
hook's own lookup table is keyed by codepoint. Hebrew is exercised explicitly: it is legitimate
non-ASCII content the hook must NOT flag, only typographic substitutions and emoji.
"""

from pathlib import Path

from check_prose import Violation, find_violations, format_report, is_emoji

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "check_prose.py"

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
RIGHT_ARROW = chr(0x2192)
ELLIPSIS = chr(0x2026)
NBSP = chr(0x00A0)
SPARKLES_EMOJI = chr(0x2728)
ALEPH = chr(0x05D0)  # Hebrew letter: legitimate non-ASCII, never a violation


class TestFindViolations:
    def test_flags_an_em_dash_with_the_ascii_double_hyphen(self):
        (violation,) = find_violations(f"a {EM_DASH} b")
        assert violation.replacement == "--"
        assert violation.char == EM_DASH

    def test_flags_a_unicode_arrow_with_an_ascii_arrow(self):
        (violation,) = find_violations(f"x {RIGHT_ARROW} y")
        assert violation.replacement == "->"

    def test_flags_en_dash_ellipsis_and_nbsp(self):
        replacements = {v.replacement for v in find_violations(f"{EN_DASH}{ELLIPSIS}{NBSP}")}
        assert replacements == {"-", "...", " "}

    def test_flags_an_emoji_with_no_ascii_replacement(self):
        (violation,) = find_violations(f"ship it {SPARKLES_EMOJI}")
        assert violation.replacement is None
        assert violation.char == SPARKLES_EMOJI

    def test_clean_ascii_is_silent(self):
        assert find_violations("plain ascii -- with an arrow -> and ... ellipsis") == []

    def test_hebrew_is_not_flagged(self):
        # Legitimate non-ASCII content; only typographic slips and emoji are violations.
        assert find_violations(f"{ALEPH}{ALEPH}{ALEPH}") == []

    def test_reports_one_indexed_line_and_column(self):
        (violation,) = find_violations(f"ok\nab{EM_DASH}cd")
        assert (violation.line, violation.column) == (2, 3)


class TestIsEmoji:
    def test_true_for_a_pictograph(self):
        assert is_emoji(SPARKLES_EMOJI)

    def test_false_for_ascii_and_hebrew(self):
        assert not is_emoji("A")
        assert not is_emoji(ALEPH)


class TestFormatReport:
    def test_names_file_line_column_and_codepoint(self):
        report = format_report("docs/x.md", [Violation(2, 3, EM_DASH, "--")])
        assert "docs/x.md:2:3" in report
        assert "U+2014" in report
        assert "`--`" in report


class TestHookFileContract:
    def test_carries_a_python3_shebang(self):
        assert HOOK.read_text().startswith("#!/usr/bin/env python3\n")

    def test_is_executable(self):
        assert HOOK.stat().st_mode & 0o111

    def test_source_is_pure_ascii(self):
        # The hook enforces ASCII typography; its own source must obey the rule it checks.
        assert HOOK.read_bytes().isascii()
