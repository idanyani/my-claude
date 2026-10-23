"""Tests for merging the repo's settings.json into the live one at install time."""

import json
import os
import subprocess

import pytest
from install_record import read_record
from merge_settings import BACKUP_SUFFIX, SETTINGS_KIND, main, merge, shipped_paths


class TestMerge:
    def test_keeps_the_live_key_order(self):
        merged, _, _, _ = merge({"b": 1, "c": 2}, {"b": 9, "a": 0})
        assert list(merged) == ["b", "a", "c"]

    def test_keeps_and_reports_a_machine_only_key(self):
        merged, kept, overwritten, _ = merge(
            {"model": "opus"}, {"model": "opus", "autoMode": {"a": 1}}
        )
        assert merged == {"model": "opus", "autoMode": {"a": 1}}
        assert kept == ["autoMode"]
        assert overwritten == {}

    def test_keeps_a_machine_only_key_nested_under_a_repo_key(self):
        merged, kept, _, _ = merge({"permissions": {"allow": []}}, {"permissions": {"deny": ["x"]}})
        assert merged == {"permissions": {"allow": [], "deny": ["x"]}}
        assert kept == ["permissions.deny"]

    def test_repo_value_wins_and_the_differing_live_value_is_reported(self):
        merged, kept, overwritten, _ = merge({"theme": "dark"}, {"theme": "light"})
        assert merged == {"theme": "dark"}
        assert kept == []
        assert overwritten == {"theme": "light"}

    def test_equal_values_are_not_reported(self):
        settings = {"theme": "dark", "hooks": {"Stop": [{"command": "x"}]}}
        assert merge(settings, json.loads(json.dumps(settings))) == (settings, [], {}, [])

    def test_replaces_lists_instead_of_unioning_them(self):
        # A union would keep a permission the repo removed on every machine forever.
        merged, _, overwritten, _ = merge(
            {"permissions": {"allow": ["a"]}}, {"permissions": {"allow": ["a", "b"]}}
        )
        assert merged == {"permissions": {"allow": ["a"]}}
        assert overwritten == {"permissions.allow": ["a", "b"]}

    def test_repo_object_replaces_a_live_scalar(self):
        merged, _, overwritten, _ = merge({"hooks": {"Stop": []}}, {"hooks": "broken"})
        assert merged == {"hooks": {"Stop": []}}
        assert overwritten == {"hooks": "broken"}

    def test_removes_and_reports_a_retired_key(self):
        merged, kept, _, removed = merge(
            {"enabledPlugins": {"a": True}},
            {"enabledPlugins": {"a": True, "old": False}},
            dropped={"/enabledPlugins/old"},
        )
        assert merged == {"enabledPlugins": {"a": True}}
        assert kept == []
        assert removed == ["enabledPlugins.old"]

    def test_removes_a_retired_object_whole_when_nothing_in_it_is_the_machines(self):
        merged, _, _, removed = merge(
            {"theme": "dark"},
            {"theme": "dark", "autoMode": {"environment": []}},
            dropped={"/autoMode", "/autoMode/environment"},
        )
        assert merged == {"theme": "dark"}
        assert removed == ["autoMode"]

    def test_keeps_a_machine_only_key_inside_a_retired_object(self):
        merged, kept, _, removed = merge(
            {},
            {"autoMode": {"environment": [], "mine": 1}},
            dropped={"/autoMode", "/autoMode/environment"},
        )
        assert merged == {"autoMode": {"mine": 1}}
        assert kept == ["autoMode.mine"]
        assert removed == ["autoMode.environment"]

    def test_a_dotted_key_is_not_confused_with_a_nested_path(self):
        merged, _, _, removed = merge({}, {"a.b": 1, "a": {"b": 2}}, dropped={"/a", "/a/b"})
        assert merged == {"a.b": 1}
        assert removed == ["a"]


class TestShippedPaths:
    def test_names_every_key_including_nested_ones_as_json_pointers(self):
        settings = {"permissions": {"allow": ["x"]}, "model": "opus"}
        assert shipped_paths(settings) == {"/permissions", "/permissions/allow", "/model"}

    def test_escapes_slashes_and_tildes(self):
        assert shipped_paths({"a/b": {"c~": 1}}) == {"/a~1b", "/a~1b/c~0"}


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
        assert main([str(repo), str(live), str(tmp_path / "record.json")]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark", "autoMode": {"a": 1}}
        assert live.read_text().endswith("}\n")
        err = capsys.readouterr().err
        assert "autoMode" in err
        assert "theme" in err

    def test_reports_the_overwritten_live_value_as_json(self, tmp_path, capsys):
        # The old value is visible where the drift is reported, without opening the backup.
        repo = tmp_path / "repo.json"
        live = tmp_path / "live.json"
        old = [{"command": "mine.sh"}]
        _write(repo, {"hooks": {"SessionStart": []}})
        _write(live, {"hooks": {"SessionStart": old}})
        _install(repo, live, tmp_path / "record.json")
        assert json.dumps(old) in capsys.readouterr().err

    def test_installs_the_repo_settings_when_no_live_file_exists(self, tmp_path, capsys):
        repo = tmp_path / "repo.json"
        live = tmp_path / "missing" / "live.json"
        live.parent.mkdir()
        repo.write_text(json.dumps({"theme": "dark"}))
        assert main([str(repo), str(live), str(tmp_path / "record.json")]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark"}
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize("broken", ["", "{trunc", "[]"])
    def test_replaces_an_unreadable_live_file_and_warns(self, repo, tmp_path, capsys, broken):
        # A file Claude Code left truncated must not abort the install; the old content is
        # already unrecoverable as settings.
        live = tmp_path / "live.json"
        live.write_text(broken)
        assert main([str(repo), str(live), str(tmp_path / "record.json")]) == 0
        assert json.loads(live.read_text()) == {"theme": "dark"}
        assert "not a JSON object" in capsys.readouterr().err

    def test_writes_through_a_symlinked_live_file(self, repo, tmp_path):
        target = tmp_path / "dotfiles" / "settings.json"
        target.parent.mkdir()
        target.write_text(json.dumps({"autoMode": {"a": 1}}))
        live = tmp_path / "live.json"
        live.symlink_to(target)
        main([str(repo), str(live), str(tmp_path / "record.json")])
        assert live.is_symlink()
        assert json.loads(target.read_text()) == {"autoMode": {"a": 1}, "theme": "dark"}

    def test_preserves_the_live_file_mode(self, repo, tmp_path):
        live = tmp_path / "live.json"
        live.write_text("{}")
        live.chmod(0o644)
        main([str(repo), str(live), str(tmp_path / "record.json")])
        assert live.stat().st_mode & 0o777 == 0o644

    def test_leaves_no_temp_file_behind(self, repo, tmp_path):
        live = tmp_path / "live.json"
        main([str(repo), str(live), str(tmp_path / "record.json")])
        assert sorted(os.listdir(tmp_path)) == ["live.json", "record.json", "repo.json"]

    def test_rejects_a_wrong_argument_count(self):
        with pytest.raises(SystemExit):
            main([])


def _write(path, settings):
    path.write_text(json.dumps(settings))


def _install(repo, live, record):
    assert main([str(repo), str(live), str(record)]) == 0


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "repo.json", tmp_path / "live.json", tmp_path / "record.json"


class TestRetiringDroppedKeys:
    def test_records_the_paths_the_repo_ships(self, paths):
        repo, live, record = paths
        _write(repo, {"enabledPlugins": {"a": True}})
        _install(repo, live, record)
        assert read_record(record)[SETTINGS_KIND] == ["/enabledPlugins", "/enabledPlugins/a"]

    def test_retires_a_key_the_repo_dropped_since_the_last_install(self, paths, capsys):
        repo, live, record = paths
        _write(repo, {"enabledPlugins": {"a": True, "old": False}})
        _install(repo, live, record)
        _write(repo, {"enabledPlugins": {"a": True}})
        _install(repo, live, record)
        assert json.loads(live.read_text()) == {"enabledPlugins": {"a": True}}
        assert "enabledPlugins.old" in capsys.readouterr().err

    def test_keeps_a_key_the_repo_never_shipped(self, paths):
        repo, live, record = paths
        _write(repo, {"theme": "dark"})
        _install(repo, live, record)
        _write(live, {"theme": "dark", "mine": 1})
        _install(repo, live, record)
        assert json.loads(live.read_text()) == {"theme": "dark", "mine": 1}

    def test_keeps_a_retired_key_the_machine_sets_again(self, paths):
        repo, live, record = paths
        _write(repo, {"theme": "dark", "old": 1})
        _install(repo, live, record)
        _write(repo, {"theme": "dark"})
        _install(repo, live, record)
        _write(live, {"theme": "dark", "old": 2})
        _install(repo, live, record)
        assert json.loads(live.read_text()) == {"theme": "dark", "old": 2}

    def test_keeps_the_records_other_kinds(self, paths):
        repo, live, record = paths
        _write(record, {"links": ["skills/x"]})
        _write(repo, {"theme": "dark"})
        _install(repo, live, record)
        assert read_record(record)["links"] == ["skills/x"]


class TestBackup:
    """The live file is backed up before a merge discards any of its values."""

    def test_backs_up_the_live_file_before_overwriting_a_value(self, paths, capsys):
        repo, live, record = paths
        _write(repo, {"theme": "dark"})
        live.write_text('{"theme": "light"}')
        _install(repo, live, record)
        backup = live.with_name(live.name + BACKUP_SUFFIX)
        assert backup.read_text() == '{"theme": "light"}'
        assert str(backup) in capsys.readouterr().err

    def test_backs_up_the_live_file_before_removing_a_retired_key(self, paths):
        repo, live, record = paths
        _write(repo, {"theme": "dark", "old": 1})
        _install(repo, live, record)
        _write(repo, {"theme": "dark"})
        _install(repo, live, record)
        backup = live.with_name(live.name + BACKUP_SUFFIX)
        assert json.loads(backup.read_text()) == {"theme": "dark", "old": 1}

    def test_writes_no_backup_when_no_live_value_is_lost(self, paths):
        repo, live, record = paths
        _write(repo, {"theme": "dark", "new": 1})
        _write(live, {"theme": "dark", "mine": 1})
        _install(repo, live, record)
        assert not live.with_name(live.name + BACKUP_SUFFIX).exists()


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


class TestBootstrappingFromHistory:
    """With no settings record yet, every path the repo's file ever shipped stands in for it."""

    def test_retires_a_key_an_earlier_commit_shipped(self, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        repo = clone / "settings.json"
        _git(clone, "init", "-q")
        _write(repo, {"theme": "dark", "enabledPlugins": {"old": False}})
        _git(clone, "add", "settings.json")
        _git(clone, "commit", "-q", "-m", "ship old")
        _write(repo, {"theme": "dark", "enabledPlugins": {}})
        _git(clone, "commit", "-q", "-am", "drop old")
        live = tmp_path / "live.json"
        _write(live, {"theme": "dark", "enabledPlugins": {"old": False}, "mine": 1})
        _install(repo, live, tmp_path / "record.json")
        assert json.loads(live.read_text()) == {"theme": "dark", "enabledPlugins": {}, "mine": 1}

    def test_retires_nothing_outside_a_git_clone(self, tmp_path):
        repo = tmp_path / "repo.json"
        live = tmp_path / "live.json"
        _write(repo, {"theme": "dark"})
        _write(live, {"theme": "dark", "mine": 1})
        _install(repo, live, tmp_path / "record.json")
        assert json.loads(live.read_text()) == {"theme": "dark", "mine": 1}

    def test_retires_nothing_without_git_installed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        repo = tmp_path / "repo.json"
        live = tmp_path / "live.json"
        _write(repo, {"theme": "dark"})
        _write(live, {"theme": "dark", "mine": 1})
        _install(repo, live, tmp_path / "record.json")
        assert json.loads(live.read_text()) == {"theme": "dark", "mine": 1}
