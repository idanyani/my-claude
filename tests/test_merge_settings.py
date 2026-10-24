"""Tests for merging the repo's settings.json into the live one at install time."""

import json
import os
import subprocess

import pytest
from install_record import read_record
from merge_settings import (
    BACKUP_SUFFIX,
    ELEMENTS_KIND,
    SETTINGS_KIND,
    main,
    merge,
    shipped_elements,
    shipped_paths,
)


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


OURS = {"hooks": [{"type": "command", "command": "ours.py"}]}
THEIRS = {"hooks": [{"type": "command", "command": "theirs.sh"}]}


def _hooks(**events):
    return {"hooks": events}


class TestMergingLists:
    """A list keeps the elements another tool or the machine added; the repo owns only the ones
    it ships or once shipped."""

    def test_keeps_and_reports_an_element_another_tool_added(self):
        repo = _hooks(SessionStart=[OURS])
        live = _hooks(SessionStart=[OURS, THEIRS])
        merged, kept, overwritten, removed = merge(repo, live)
        assert merged == live
        assert kept == [f"hooks.SessionStart {json.dumps(THEIRS, sort_keys=True)}"]
        assert overwritten == {}
        assert removed == []

    def test_merging_its_own_result_again_changes_nothing(self):
        repo = _hooks(SessionStart=[OURS])
        first = merge(repo, _hooks(SessionStart=[THEIRS])).merged
        merged, _, overwritten, _ = merge(repo, first)
        assert merged == first
        assert overwritten == {}

    def test_keeps_the_live_element_order_and_appends_missing_repo_elements(self):
        merged, _, overwritten, _ = merge({"a": ["x", "y", "z"]}, {"a": ["y", "x"]})
        assert merged == {"a": ["y", "x", "z"]}
        assert overwritten == {}

    def test_keeps_an_owned_element_the_repo_still_ships(self):
        repo = {"a": ["x"]}
        assert merge(repo, {"a": ["x"]}, owned=shipped_elements(repo)) == (repo, [], {}, [])

    def test_reports_a_kept_element_as_canonical_json(self):
        _, kept, _, _ = merge({"a": []}, {"a": [{"b": 1, "a": 2}]})
        assert kept == ['a {"a": 2, "b": 1}']

    def test_identifies_an_element_regardless_of_its_key_order(self):
        repo = {"list": [{"a": 1, "b": 2}]}
        merged, kept, _, _ = merge(repo, {"list": [{"b": 2, "a": 1}]})
        assert merged == repo
        assert kept == []

    def test_removes_an_element_the_repo_once_shipped(self):
        # Keeping it would keep a permission the repo removed on every machine forever.
        owned = shipped_elements({"permissions": {"allow": ["old"]}})
        merged, _, overwritten, _ = merge(
            {"permissions": {"allow": ["a"]}},
            {"permissions": {"allow": ["old", "mine"]}},
            owned=owned,
        )
        assert merged == {"permissions": {"allow": ["mine", "a"]}}
        assert overwritten == {"permissions.allow": ["old", "mine"]}

    def test_keeps_the_foreign_elements_of_a_list_the_repo_dropped(self):
        merged, kept, overwritten, _ = merge(
            {},
            _hooks(Stop=[OURS, THEIRS]),
            dropped={"/hooks", "/hooks/Stop"},
            owned=shipped_elements(_hooks(Stop=[OURS])),
        )
        assert merged == _hooks(Stop=[THEIRS])
        assert kept == [f"hooks.Stop {json.dumps(THEIRS, sort_keys=True)}"]
        assert overwritten == {"hooks.Stop": [OURS, THEIRS]}

    def test_removes_a_dropped_list_whole_when_the_repo_owns_every_element(self):
        merged, _, _, removed = merge(
            {"theme": "dark"},
            {"theme": "dark", "old": ["x"]},
            dropped={"/old"},
            owned=shipped_elements({"old": ["x"]}),
        )
        assert merged == {"theme": "dark"}
        assert removed == ["old"]

    def test_repo_list_replaces_a_live_value_that_is_not_a_list(self):
        repo = _hooks(Stop=[OURS])
        merged, _, overwritten, _ = merge(repo, _hooks(Stop="broken"))
        assert merged == repo
        assert overwritten == {"hooks.Stop": "broken"}


class TestShippedElements:
    def test_names_every_list_element_under_its_lists_json_pointer(self):
        settings = {"permissions": {"allow": ["x"]}, "model": "opus"}
        assert shipped_elements(settings) == {'/permissions/allow/"x"'}

    def test_escapes_slashes_in_an_element(self):
        assert shipped_elements({"a": ["b/c"]}) == {'/a/"b~1c"'}


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
        old = {"type": "command", "command": "mine.sh"}
        _write(repo, {"statusLine": "none"})
        _write(live, {"statusLine": old})
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

    def test_a_repeated_install_rewrites_neither_the_live_file_nor_the_record(self, repo, tmp_path):
        # Every running session's settings watcher sees a replaced file, even an identical one.
        live = tmp_path / "live.json"
        record = tmp_path / "record.json"
        _install(repo, live, record)
        before = live.stat().st_ino, record.stat().st_ino
        _install(repo, live, record)
        assert (live.stat().st_ino, record.stat().st_ino) == before


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


class TestRetiringDroppedElements:
    def test_records_the_list_elements_the_repo_ships(self, paths):
        repo, live, record = paths
        settings = {"permissions": {"allow": ["a"]}}
        _write(repo, settings)
        _install(repo, live, record)
        assert read_record(record)[ELEMENTS_KIND] == sorted(shipped_elements(settings))

    def test_retires_an_element_the_repo_dropped_and_keeps_another_tools(self, paths):
        repo, live, record = paths
        _write(repo, _hooks(SessionStart=[OURS]))
        _install(repo, live, record)
        _write(live, _hooks(SessionStart=[OURS, THEIRS]))
        _write(repo, _hooks(SessionStart=[]))
        _install(repo, live, record)
        assert json.loads(live.read_text()) == _hooks(SessionStart=[THEIRS])

    def test_writes_no_backup_for_an_element_another_tool_added(self, paths):
        repo, live, record = paths
        _write(repo, _hooks(SessionStart=[OURS]))
        _write(live, _hooks(SessionStart=[OURS, THEIRS]))
        _install(repo, live, record)
        assert not live.with_name(live.name + BACKUP_SUFFIX).exists()


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

    def test_backs_up_a_live_file_that_is_not_a_json_object(self, paths):
        repo, live, record = paths
        _write(repo, {"theme": "dark"})
        live.write_text('{"theme": "light",}')
        _install(repo, live, record)
        backup = live.with_name(live.name + BACKUP_SUFFIX)
        assert backup.read_text() == '{"theme": "light",}'

    def test_keeps_the_live_file_mode_on_the_backup(self, paths):
        # The live file may hold tokens under "env"; the backup must not widen who can read them.
        repo, live, record = paths
        _write(repo, {"theme": "dark"})
        _write(live, {"theme": "light"})
        live.chmod(0o600)
        _install(repo, live, record)
        assert live.with_name(live.name + BACKUP_SUFFIX).stat().st_mode & 0o777 == 0o600

    def test_backs_up_next_to_the_target_of_a_symlinked_live_file(self, paths, tmp_path):
        repo, live, record = paths
        target = tmp_path / "dotfiles" / "settings.json"
        target.parent.mkdir()
        _write(target, {"theme": "light"})
        live.symlink_to(target)
        _write(repo, {"theme": "dark"})
        _install(repo, live, record)
        assert json.loads(target.with_name(target.name + BACKUP_SUFFIX).read_text()) == {
            "theme": "light"
        }

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


def _commit_history(clone, *versions):
    """Commit each settings version in turn to a new clone; return its settings file."""
    clone.mkdir()
    repo = clone / "settings.json"
    _git(clone, "init", "-q")
    for version in versions:
        _write(repo, version)
        _git(clone, "add", "settings.json")
        _git(clone, "commit", "-q", "-m", "version")
    return repo


class TestBootstrappingFromHistory:
    """With no settings record yet, every path the repo's file ever shipped stands in for it."""

    def test_retires_a_key_an_earlier_commit_shipped(self, tmp_path):
        repo = _commit_history(
            tmp_path / "clone",
            {"theme": "dark", "enabledPlugins": {"old": False}},
            {"theme": "dark", "enabledPlugins": {}},
        )
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

    def test_retires_a_list_element_an_earlier_commit_shipped(self, tmp_path):
        # A record from before list elements were recorded holds only the "settings" kind.
        repo = _commit_history(tmp_path / "clone", {"allow": ["old"]}, {"allow": ["a"]})
        live = tmp_path / "live.json"
        record = tmp_path / "record.json"
        _write(record, {SETTINGS_KIND: ["/allow"]})
        _write(live, {"allow": ["old", "mine"]})
        _install(repo, live, record)
        assert json.loads(live.read_text()) == {"allow": ["mine", "a"]}
