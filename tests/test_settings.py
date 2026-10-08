"""Contract checks on the shipped dot-claude/settings.json."""

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "dot-claude" / "settings.json"

# A list without this marker replaces Claude Code's built-in auto-mode entries instead of
# extending them, so updates to the built-ins would stop arriving.
DEFAULTS_MARKER = "$defaults"


class TestAutoMode:
    def test_every_list_extends_the_built_in_entries(self):
        auto_mode = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["autoMode"]
        lists = {k: v for k, v in auto_mode.items() if isinstance(v, list)}
        assert lists, "autoMode defines no lists"
        for name, entries in lists.items():
            assert DEFAULTS_MARKER in entries, f"autoMode.{name} drops the built-in entries"
