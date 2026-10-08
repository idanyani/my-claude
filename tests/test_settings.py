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


# Credential stores a session must neither read nor modify. Writing to a shell rc file or
# authorized_keys would plant persistence, so Edit is denied alongside Read.
CREDENTIAL_PATHS = [
    "~/.ssh/**",
    "~/.aws/**",
    "~/.config/gh/**",
    "~/.docker/config.json",
    "~/.gnupg/**",
    "~/.netrc",
    "~/.git-credentials",
    "~/.npmrc",
    "~/.pypirc",
    "~/.bashrc",
    "~/.zshrc",
    "~/.profile",
    "~/.bash_profile",
]
DENIED_TOOLS = ["Read", "Edit"]


class TestCredentialDeny:
    def test_every_credential_path_is_denied_to_every_file_tool(self):
        permissions = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["permissions"]
        deny = set(permissions.get("deny", []))
        missing = [
            f"{tool}({path})"
            for path in CREDENTIAL_PATHS
            for tool in DENIED_TOOLS
            if f"{tool}({path})" not in deny
        ]
        assert not missing, f"permissions.deny lacks {missing}"
