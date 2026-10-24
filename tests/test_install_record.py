"""Tests for the install record that lets a later install retire what the repo dropped."""

import json
import os

import pytest
from install_record import read_record, retired, write_atomically, write_kind


class TestRetired:
    def test_returns_the_recorded_entries_no_longer_shipped_sorted(self):
        assert retired({"b", "a", "kept"}, {"kept", "new"}) == ["a", "b"]

    def test_retires_nothing_when_nothing_was_recorded(self):
        assert retired(set(), {"new"}) == []


class TestReadRecord:
    def test_reads_a_written_kind(self, tmp_path):
        path = tmp_path / "record.json"
        write_kind(path, "links", {"b", "a"})
        assert read_record(path) == {"links": ["a", "b"]}

    def test_a_missing_file_is_an_empty_record(self, tmp_path):
        assert read_record(tmp_path / "missing.json") == {}

    @pytest.mark.parametrize("broken", ["", "{trunc", "[]"])
    def test_an_unreadable_file_is_an_empty_record(self, tmp_path, broken):
        path = tmp_path / "record.json"
        path.write_text(broken)
        assert read_record(path) == {}

    def test_a_non_utf8_file_is_an_empty_record(self, tmp_path):
        path = tmp_path / "record.json"
        path.write_bytes(b"\xff")
        assert read_record(path) == {}

    def test_drops_only_a_malformed_kind(self, tmp_path):
        path = tmp_path / "record.json"
        path.write_text(json.dumps({"links": ["a"], "settings": [1]}))
        assert read_record(path) == {"links": ["a"]}


class TestWriteKind:
    def test_keeps_every_other_kind(self, tmp_path):
        path = tmp_path / "record.json"
        write_kind(path, "settings", {"theme"})
        write_kind(path, "links", {"CLAUDE.md"})
        write_kind(path, "links", set())
        assert json.loads(path.read_text()) == {"settings": ["theme"], "links": []}

    def test_rewrites_nothing_when_the_kind_is_unchanged(self, tmp_path):
        path = tmp_path / "record.json"
        write_kind(path, "links", {"a"})
        before = path.stat().st_ino
        write_kind(path, "links", {"a"})
        assert path.stat().st_ino == before


class TestWriteAtomically:
    """A write whose content and mode the file already has leaves the file in place, so a
    watcher sees no change."""

    def test_leaves_a_file_with_the_same_content_in_place(self, tmp_path):
        path = tmp_path / "settings.json"
        write_atomically(path, b"{}\n")
        before = path.stat().st_ino
        write_atomically(path, b"{}\n")
        assert path.stat().st_ino == before

    def test_replaces_a_file_with_different_content(self, tmp_path):
        path = tmp_path / "settings.json"
        write_atomically(path, b"{}\n")
        write_atomically(path, b"[]\n")
        assert path.read_bytes() == b"[]\n"

    def test_leaves_an_owner_only_file_with_the_same_content_in_place(self, tmp_path):
        path = tmp_path / "settings.json"
        write_atomically(path, b"{}\n", mode=0o600)
        before = path.stat().st_ino
        write_atomically(path, b"{}\n")
        assert path.stat().st_ino == before

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
    def test_replaces_a_file_it_cannot_read(self, tmp_path):
        path = tmp_path / "settings.json"
        write_atomically(path, b"{}\n", mode=0o200)
        write_atomically(path, b"[]\n")
        path.chmod(0o600)
        assert path.read_bytes() == b"[]\n"

    def test_applies_a_new_mode_to_a_file_with_the_same_content(self, tmp_path):
        path = tmp_path / "settings.json"
        write_atomically(path, b"{}\n", mode=0o644)
        write_atomically(path, b"{}\n", mode=0o600)
        assert path.stat().st_mode & 0o777 == 0o600
