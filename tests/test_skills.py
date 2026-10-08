"""Contract checks on the shipped skills' SKILL.md files."""

import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent / "dot-claude" / "skills"
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))

# Claude Code substitutes this variable in both the body and the allowed-tools Bash rules, so a
# body command written with it is the exact text its rule matches, on any machine.
SKILL_DIR_VARIABLE = "${CLAUDE_SKILL_DIR}"
SCRIPT_CALL = re.compile(r"python3 (\S+?)/scripts/([\w<>]+)\.py")


def _split(skill_file: Path) -> tuple[list[str], str]:
    """Return the frontmatter lines and the body of a SKILL.md."""
    _, frontmatter, body = skill_file.read_text(encoding="utf-8").split("---\n", 2)
    return frontmatter.splitlines(), body


def _allowed_tools(frontmatter: list[str]) -> set[str]:
    if "allowed-tools:" not in frontmatter:
        return set()
    start = frontmatter.index("allowed-tools:") + 1
    rules = set()
    for line in frontmatter[start:]:
        if not line.startswith("  - "):
            break
        rules.add(line.removeprefix("  - "))
    return rules


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: p.parent.name)
class TestScriptCalls:
    def test_scripts_are_called_through_the_skill_dir_variable(self, skill_file):
        _, body = _split(skill_file)
        prefixes = {prefix for prefix, _ in SCRIPT_CALL.findall(body)}
        assert prefixes <= {SKILL_DIR_VARIABLE}

    def test_every_called_script_is_pre_approved(self, skill_file):
        frontmatter, body = _split(skill_file)
        names = {name for _, name in SCRIPT_CALL.findall(body) if name.isidentifier()}
        if not names:
            pytest.skip("skill calls no scripts")
        rules = _allowed_tools(frontmatter)
        missing = [
            name
            for name in sorted(names)
            if f"Bash(python3 {SKILL_DIR_VARIABLE}/scripts/{name}.py *)" not in rules
        ]
        assert not missing
