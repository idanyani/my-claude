"""Tests for merging the repo's settings.json into the live one at install time."""

import json
import os

import pytest
from merge_settings import main, merge


class TestMerge:
    def test_keeps_the_live_key_order(self):
        merged, _, _ = merge({"b": 1, "c": 2}, {"b": 9, "a": 0})
        assert list(merged) == ["b", "a", "c"]

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
    @pytest.fixture
    def repo(self, tmp_path):
        repo = tmp_path / "repo.json"
        repo.write_text(json.dumps({"theme": "dark"}))
        return repo

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

    @pytest.mark.parametrize("broken", ["", "{trunc", "[]"])
    def test_replaces_an_unreadable_live_file_and_warns(self, repo, tmp_path, capsys, broken):
        # A file Claude Code left truncated must not abort the install; the old content is
        # already unrecoverable as settings.
        live = tmp_path / "live.json"
        live.write_text(broken)
        assert main([str(repo), str(live)]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark"}
        assert "not a JSON object" in capsys.readouterr().err

    def test_writes_through_a_symlinked_live_file(self, repo, tmp_path):
        target = tmp_path / "dotfiles" / "settings.json"
        target.parent.mkdir()
        target.write_text(json.dumps({"autoMode": {"a": 1}}))
        live = tmp_path / "live.json"
        live.symlink_to(target)
        main([str(repo), str(live)])
        assert live.is_symlink()
        assert json.loads(target.read_text()) == {"autoMode": {"a": 1}, "theme": "dark"}

    def test_preserves_the_live_file_mode(self, repo, tmp_path):
        live = tmp_path / "live.json"
        live.write_text("{}")
        live.chmod(0o644)
        main([str(repo), str(live)])
        assert live.stat().st_mode & 0o777 == 0o644

    def test_leaves_no_temp_file_behind(self, repo, tmp_path):
        live = tmp_path / "live.json"
        main([str(repo), str(live)])
        assert sorted(os.listdir(tmp_path)) == ["live.json", "repo.json"]

    def test_rejects_a_wrong_argument_count(self):
        with pytest.raises(SystemExit):
            main([])
