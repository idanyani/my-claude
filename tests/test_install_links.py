"""Tests for symlinking dot-claude/ into ~/.claude and retiring links the repo dropped."""

import os
import shutil
from pathlib import Path

import pytest
from install_links import install, is_retirable, links_into, main, planned_links
from install_record import read_record


@pytest.fixture
def src(tmp_path: Path) -> Path:
    src = tmp_path / "repo" / "dot-claude"
    (src / "skills" / "keep").mkdir(parents=True)
    (src / "skills" / "drop").mkdir()
    (src / "CLAUDE.md").write_text("rules")
    (src / "settings.json").write_text("{}")
    return src


@pytest.fixture
def dest(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude"


@pytest.fixture
def record(dest: Path) -> Path:
    return dest / "record.json"


MERGED = frozenset({"settings.json"})


class TestPlannedLinks:
    def test_links_files_whole_and_directories_per_child_except_merged_ones(self, src):
        assert planned_links(src, MERGED) == {
            "CLAUDE.md": src / "CLAUDE.md",
            "skills/drop": src / "skills" / "drop",
            "skills/keep": src / "skills" / "keep",
        }

    def test_skips_hidden_entries(self, src):
        (src / ".hidden").write_text("")
        (src / "skills" / ".hidden").mkdir()
        assert ".hidden" not in planned_links(src, MERGED)
        assert "skills/.hidden" not in planned_links(src, MERGED)


class TestInstall:
    def test_links_every_planned_entry(self, src, dest, record):
        install(src, dest, record, MERGED)
        assert (dest / "CLAUDE.md").readlink() == src / "CLAUDE.md"
        assert (dest / "skills" / "keep").readlink() == src / "skills" / "keep"
        assert not (dest / "settings.json").exists()

    def test_heals_a_link_that_points_elsewhere(self, src, dest, record, tmp_path):
        dest.mkdir(parents=True)
        (dest / "CLAUDE.md").symlink_to(tmp_path / "old-clone" / "CLAUDE.md")
        install(src, dest, record, MERGED)
        assert (dest / "CLAUDE.md").readlink() == src / "CLAUDE.md"

    def test_keeps_a_link_that_already_points_at_its_target(self, src, dest, record):
        install(src, dest, record, MERGED)
        before = os.lstat(dest / "CLAUDE.md").st_ino
        install(src, dest, record, MERGED)
        assert os.lstat(dest / "CLAUDE.md").st_ino == before

    def test_replaces_a_link_to_a_repo_file_that_became_a_directory(self, src, dest, record):
        # Linking the children through the old link would write into the repo itself.
        (src / "agents").write_text("")
        install(src, dest, record, MERGED)
        (src / "agents").unlink()
        (src / "agents").mkdir()
        (src / "agents" / "a.md").write_text("agent")
        install(src, dest, record, MERGED)
        assert not (dest / "agents").is_symlink()
        assert (dest / "agents" / "a.md").readlink() == src / "agents" / "a.md"
        assert (src / "agents" / "a.md").read_text() == "agent"

    def test_does_not_record_a_link_a_directory_blocked(self, src, dest, record):
        (dest / "skills" / "keep").mkdir(parents=True)
        install(src, dest, record, MERGED)
        assert "skills/keep" not in read_record(record)["links"]

    def test_leaves_a_directory_in_the_way_of_a_link(self, src, dest, record, capsys):
        (dest / "skills" / "keep").mkdir(parents=True)
        install(src, dest, record, MERGED)
        assert not (dest / "skills" / "keep").is_symlink()
        assert sorted(p.name for p in (dest / "skills").iterdir()) == ["drop", "keep"]
        assert "a directory is in the way" in capsys.readouterr().err

    def test_retires_the_link_to_an_entry_the_repo_dropped(self, src, dest, record, capsys):
        install(src, dest, record, MERGED)
        shutil.rmtree(src / "skills" / "drop")
        install(src, dest, record, MERGED)
        assert not (dest / "skills" / "drop").is_symlink()
        assert (dest / "skills" / "keep").is_symlink()
        assert "skills/drop" in capsys.readouterr().err

    def test_retires_a_dangling_link_an_unrecorded_install_left(self, src, dest, record):
        # Machines installed before the record existed carry such links with no record entry.
        install(src, dest, record, MERGED)
        record.unlink()
        shutil.rmtree(src / "skills" / "drop")
        install(src, dest, record, MERGED)
        assert not (dest / "skills" / "drop").is_symlink()

    def test_records_what_it_linked(self, src, dest, record):
        install(src, dest, record, MERGED)
        assert read_record(record)["links"] == ["CLAUDE.md", "skills/drop", "skills/keep"]

    def test_keeps_a_machine_local_entry_that_replaced_a_recorded_link(self, src, dest, record):
        install(src, dest, record, MERGED)
        shutil.rmtree(src / "skills" / "drop")
        (dest / "skills" / "drop").unlink()
        (dest / "skills" / "drop").mkdir()
        install(src, dest, record, MERGED)
        assert (dest / "skills" / "drop").is_dir()

    def test_keeps_a_machine_local_dangling_link_outside_the_repo(
        self, src, dest, record, tmp_path
    ):
        dest.mkdir(parents=True)
        (dest / "local").symlink_to(tmp_path / "gone")
        install(src, dest, record, MERGED)
        assert (dest / "local").is_symlink()


class TestLinksInto:
    def test_finds_links_into_the_repo_at_the_depths_install_creates(self, src, dest, tmp_path):
        (dest / "skills").mkdir(parents=True)
        (dest / "CLAUDE.md").symlink_to(src / "CLAUDE.md")
        (dest / "skills" / "gone").symlink_to(src / "skills" / "gone")
        (dest / "skills" / "local").symlink_to(tmp_path / "elsewhere")
        assert links_into(dest, src) == {"CLAUDE.md", "skills/gone"}

    def test_a_missing_destination_has_no_links(self, src, dest):
        assert links_into(dest, src) == set()


class TestIsRetirable:
    def test_a_dangling_link_into_the_repo_is_retirable(self, src, dest):
        dest.mkdir(parents=True)
        (dest / "gone").symlink_to(src / "gone")
        assert is_retirable(dest / "gone", src)

    def test_a_relative_dangling_link_into_the_repo_is_retirable(self, src, dest):
        dest.mkdir(parents=True)
        (dest / "gone").symlink_to(Path("..") / ".." / "repo" / "dot-claude" / "gone")
        assert is_retirable(dest / "gone", src)

    def test_a_live_link_into_the_repo_is_not(self, src, dest):
        dest.mkdir(parents=True)
        (dest / "CLAUDE.md").symlink_to(src / "CLAUDE.md")
        assert not is_retirable(dest / "CLAUDE.md", src)

    def test_a_dangling_link_outside_the_repo_is_not(self, src, dest, tmp_path):
        dest.mkdir(parents=True)
        (dest / "gone").symlink_to(tmp_path / "repo" / "dot-claude-old" / "gone")
        assert not is_retirable(dest / "gone", src)

    def test_a_regular_file_is_not(self, src, dest):
        dest.mkdir(parents=True)
        (dest / "file").write_text("")
        assert not is_retirable(dest / "file", src)

    def test_a_missing_path_is_not(self, src, dest):
        assert not is_retirable(dest / "missing", src)


class TestMain:
    def test_installs_from_arguments(self, src, dest, record):
        assert main([str(src), str(dest), str(record), "--merged", "settings.json"]) == 0
        assert (dest / "CLAUDE.md").is_symlink()
        assert not (dest / "settings.json").exists()

    def test_rejects_a_wrong_argument_count(self):
        with pytest.raises(SystemExit):
            main([])
