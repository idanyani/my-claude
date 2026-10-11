"""Tests for the install record that lets a later install retire what the repo dropped."""

import json

import pytest
from install_record import read_record, retired, write_kind


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

    @pytest.mark.parametrize("broken", ["", "{trunc", "[]", '{"links": "a"}'])
    def test_an_unreadable_file_is_an_empty_record(self, tmp_path, broken):
        path = tmp_path / "record.json"
        path.write_text(broken)
        assert read_record(path) == {}


class TestWriteKind:
    def test_keeps_every_other_kind(self, tmp_path):
        path = tmp_path / "record.json"
        write_kind(path, "settings", {"theme"})
        write_kind(path, "links", {"CLAUDE.md"})
        write_kind(path, "links", set())
        assert json.loads(path.read_text()) == {"settings": ["theme"], "links": []}
