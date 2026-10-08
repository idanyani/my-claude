"""Contract checks on the shipped dot-claude/settings.json."""

import json
import re
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


# Files that hold secrets, or that export them (the shell rc files): reading one leaks the
# secret and editing one plants code, so both Read and Edit are denied.
SECRET_PATHS = [
    "~/.ssh/**",
    "~/.aws/**",
    "~/.config/gh/**",
    "~/.claude/.credentials.json",
    "~/.docker/config.json",
    "~/.gnupg/**",
    "~/.kube/**",
    "~/.config/gcloud/**",
    "~/.azure/**",
    "~/.netrc",
    "~/.git-credentials",
    "~/.config/git/credentials",
    "~/.npmrc",
    "~/.pypirc",
    "~/.pgpass",
    "~/.bashrc",
    "~/.zshrc",
    "~/.profile",
    "~/.bash_profile",
]
# Files whose contents run as code later (shell startup, git hooks and helpers, Claude Code's
# own hooks and permissions) but hold no secrets: only Edit is denied.
CODE_PATHS = [
    "~/.bash_aliases",
    "~/.bash_login",
    "~/.zshenv",
    "~/.zprofile",
    "~/.gitconfig",
    "~/.config/git/config",
    "~/.claude/settings.json",
]


def _deny_rules() -> set[str]:
    permissions = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["permissions"]
    return set(permissions.get("deny", []))


def _missing(tool: str, paths: list[str]) -> list[str]:
    deny = _deny_rules()
    return [f"{tool}({path})" for path in paths if f"{tool}({path})" not in deny]


class TestDenyRules:
    def test_secret_paths_are_denied_to_read(self):
        assert not _missing("Read", SECRET_PATHS)

    def test_secret_and_code_paths_are_denied_to_edit(self):
        assert not _missing("Edit", SECRET_PATHS + CODE_PATHS)


# The same file installs on every machine and into Tiki's image, whose home directories differ,
# so a rule naming one home directory never matches anywhere else.
HOME_DIR_PATH = re.compile(r"(?<![\w./])/(home|Users)/\w|(?<![\w./])/root\b")


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in _strings(k) + _strings(v)]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []


class TestPortability:
    def test_no_value_names_a_home_directory(self):
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        assert not [s for s in _strings(settings) if HOME_DIR_PATH.search(s)]


class TestPlugins:
    def test_each_plugin_is_enabled_from_one_marketplace(self):
        # install.sh keeps keys the repo lacks, so a plugin is retired by setting it to false.
        plugins = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["enabledPlugins"]
        names = [key.split("@")[0] for key, enabled in plugins.items() if enabled]
        assert not {name for name in names if names.count(name) > 1}
