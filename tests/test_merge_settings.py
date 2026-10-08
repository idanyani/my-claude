"""Tests for merging the repo's settings.json into the live one at install time."""

import json
from pathlib import Path

import pytest
from merge_settings import main, merge

SCRIPT = Path(__file__).parent.parent / "scripts" / "merge_settings.py"


class TestMerge:
    def test_keeps_and_reports_a_machine_only_key(self):
        merged, kept, overwritten = merge(
            {"model": "opus"}, {"model": "opus", "autoMode": {"a": 1}}
        )
        assert merged == {"model": "opus", "autoMode": {"a": 1}}
        assert kept == ["autoMode"]
        assert overwritten == []

    def test_keeps_a_machine_only_key_nested_under_a_repo_key(self):
        merged, kept, _ = merge({"permissions": {"allow": []}}, {"permissions": {"deny": ["x"]}})
        assert merged == {"permissions": {"allow": [], "deny": ["x"]}}
        assert kept == ["permissions.deny"]

    def test_repo_value_wins_and_the_differing_live_value_is_reported(self):
        merged, kept, overwritten = merge({"theme": "dark"}, {"theme": "light"})
        assert merged == {"theme": "dark"}
        assert kept == []
        assert overwritten == ["theme"]

    def test_equal_values_are_not_reported(self):
        settings = {"theme": "dark", "hooks": {"Stop": [{"command": "x"}]}}
        assert merge(settings, json.loads(json.dumps(settings))) == (settings, [], [])

    def test_replaces_lists_instead_of_unioning_them(self):
        # A union would keep a permission the repo removed on every machine forever.
        merged, _, overwritten = merge(
            {"permissions": {"allow": ["a"]}}, {"permissions": {"allow": ["a", "b"]}}
        )
        assert merged == {"permissions": {"allow": ["a"]}}
        assert overwritten == ["permissions.allow"]

    def test_repo_object_replaces_a_live_scalar(self):
        merged, _, overwritten = merge({"hooks": {"Stop": []}}, {"hooks": "broken"})
        assert merged == {"hooks": {"Stop": []}}
        assert overwritten == ["hooks"]


class TestMain:
    def test_merges_into_the_live_file_and_reports_drift(self, tmp_path, capsys):
        repo = tmp_path / "repo.json"
        live = tmp_path / "live.json"
        repo.write_text(json.dumps({"theme": "dark"}))
        live.write_text(json.dumps({"theme": "light", "autoMode": {"a": 1}}))
        assert main([str(repo), str(live)]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark", "autoMode": {"a": 1}}
        assert live.read_text().endswith("}\n")
        err = capsys.readouterr().err
        assert "autoMode" in err
        assert "theme" in err

    def test_installs_the_repo_settings_when_no_live_file_exists(self, tmp_path, capsys):
        repo = tmp_path / "repo.json"
        live = tmp_path / "missing" / "live.json"
        live.parent.mkdir()
        repo.write_text(json.dumps({"theme": "dark"}))
        assert main([str(repo), str(live)]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark"}
        assert capsys.readouterr().err == ""

    def test_rejects_a_wrong_argument_count(self):
        with pytest.raises(SystemExit):
            main([])


class TestExecutable:
    def test_carries_a_python3_shebang(self):
        assert SCRIPT.read_text().startswith("#!/usr/bin/env python3\n")

    def test_is_executable(self):
        assert SCRIPT.stat().st_mode & 0o111
