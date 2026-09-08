"""Tests for the self-matching process-pattern hook.

The bug being guarded: `pgrep -f` matches whole command lines, so a shell whose own argv
contains the pattern always finds itself. A wait loop built on one can never exit -- the
failure that motivated this hook left ten shells spinning for eleven hours.
"""

from pathlib import Path

from check_pgrep_pattern import SelfMatch, bracket_escape, find_self_matches, format_denial

HOOK = Path(__file__).parent.parent / "dot-claude" / "hooks" / "check_pgrep_pattern.py"


class TestFindSelfMatches:
    def test_flags_the_wait_loop_that_motivated_the_hook(self):
        (match,) = find_self_matches('until ! pgrep -f "bin/pytest -q"; do sleep 15; done')
        assert match.pattern == "bin/pytest -q"
        assert match.suggestion == "[b]in/pytest -q"

    def test_a_heredoc_body_is_data_not_command(self):
        # Documenting the bug must not trip the check: text fed to a command on stdin is never
        # executed. Caught when this hook blocked the pull request that introduces it.
        command = (
            "gh pr create --body-file - <<'BODYEOF'\n"
            'until ! pgrep -f "bin/pytest -q"; do sleep 15; done\n'
            "BODYEOF"
        )
        assert find_self_matches(command) == []

    def test_a_real_invocation_after_a_heredoc_is_still_flagged(self):
        command = "cat <<'EOF'\ndocs\nEOF\npgrep -f pytest"
        (match,) = find_self_matches(command)
        assert match.pattern == "pytest"

    def test_a_redirection_target_is_not_mistaken_for_the_pattern(self):
        # `>/dev/null` tokenizes as an operator plus a word; neither is a pgrep operand.
        (match,) = find_self_matches(
            'until ! pgrep -f "bin/pytest -q" >/dev/null; do sleep 15; done'
        )
        assert match.pattern == "bin/pytest -q"

    def test_a_file_descriptor_prefix_is_not_mistaken_for_the_pattern(self):
        # `2>/dev/null` puts the descriptor in a token of its own, ahead of the operator.
        (match,) = find_self_matches("pgrep -f pytest 2>/dev/null")
        assert match.pattern == "pytest"

    def test_flags_pkill_the_same_way(self):
        (match,) = find_self_matches("pkill -f 'until ! pgrep'")
        assert match.pattern == "until ! pgrep"

    def test_bracketed_pattern_is_allowed(self):
        assert find_self_matches('pgrep -f "[b]in/pytest -q"') == []

    def test_bracketed_pkill_pattern_is_allowed(self):
        assert find_self_matches("pkill -f 'until ! [p]grep'") == []

    def test_without_full_flag_there_is_no_self_match(self):
        # Without -f, pgrep matches the process name only, never the caller's command line.
        assert find_self_matches("pgrep -x pytest") == []
        assert find_self_matches("pgrep pytest") == []

    def test_long_form_full_flag_is_flagged(self):
        (match,) = find_self_matches("pgrep --full pytest")
        assert match.pattern == "pytest"

    def test_combined_short_option_cluster_is_flagged(self):
        (match,) = find_self_matches("pgrep -af pytest")
        assert match.pattern == "pytest"

    def test_an_option_value_is_never_mistaken_for_the_pattern(self):
        # getopt permutes, so the value may sit on either side of the pattern operand.
        (before,) = find_self_matches("pgrep -u root -f pytest")
        (after,) = find_self_matches("pgrep -f pytest -u root")
        assert before.pattern == after.pattern == "pytest"

    def test_bare_unquoted_pattern_is_flagged(self):
        (match,) = find_self_matches("pgrep -f pytest")
        assert match.pattern == "pytest"

    def test_reports_every_offending_invocation(self):
        matches = find_self_matches('pgrep -f alpha && pkill -f "[b]eta" ; pgrep -f gamma')
        assert [m.pattern for m in matches] == ["alpha", "gamma"]

    def test_a_shell_variable_pattern_is_not_statically_provable(self):
        # The caller's argv holds `$PATTERN`, not its value, so this does not self-match.
        assert find_self_matches('pgrep -f "$PATTERN"') == []

    def test_unparsable_quoting_is_left_alone(self):
        assert find_self_matches("pgrep -f 'unbalanced") == []

    def test_unrelated_commands_are_silent(self):
        assert find_self_matches("uv run pytest -q") == []
        assert find_self_matches("grep -f patterns.txt file.txt") == []


class TestBracketEscape:
    def test_brackets_the_first_alphanumeric_character(self):
        assert bracket_escape("pytest") == "[p]ytest"

    def test_skips_leading_punctuation(self):
        assert bracket_escape("^/usr/bin") == "^/[u]sr/bin"

    def test_returns_the_pattern_unchanged_when_it_has_no_alphanumeric(self):
        assert bracket_escape("---") == "---"


class TestFormatDenial:
    def test_names_the_pattern_and_its_bracketed_replacement(self):
        reason = format_denial([SelfMatch("pytest", "[p]ytest")])
        assert "pytest" in reason
        assert "[p]ytest" in reason


class TestHookFileContract:
    def test_carries_a_python3_shebang(self):
        assert HOOK.read_text().startswith("#!/usr/bin/env python3\n")

    def test_is_executable(self):
        assert HOOK.stat().st_mode & 0o111

    def test_source_is_pure_ascii(self):
        assert HOOK.read_bytes().isascii()
