import datetime
import json
import os

import pytest

from mktsk.reminders import (
    add,
    for_task,
    load,
    pop_due,
    reminders_path,
    remove,
)


def _due(y, m, d, h, mi):
    return datetime.datetime(y, m, d, h, mi)  # noqa: DTZ001


def test_add_then_load_round_trip_sorted_by_due(tmp_path):
    path = tmp_path / "reminders.json"
    first = add(path, _due(2026, 10, 27, 9, 0), "first", "261027 - Alpha", "Alpha")
    second = add(path, _due(2026, 10, 27, 8, 0), "second", "261027 - Beta", "Beta")

    reminders = load(path)
    assert [r.id for r in reminders] == [second.id, first.id]
    assert reminders[0].due == _due(2026, 10, 27, 8, 0)
    assert reminders[1].due == _due(2026, 10, 27, 9, 0)


def test_unicode_message_round_trip(tmp_path):
    path = tmp_path / "reminders.json"
    reminder = add(path, _due(2026, 10, 27, 9, 0), "café ☕", "261027 - Alpha", "Alpha")

    assert load(path) == [reminder]
    text = path.read_text(encoding="utf-8")
    assert "café ☕" in text


def test_for_task_filters_by_task_folder_name(tmp_path):
    path = tmp_path / "reminders.json"
    add(path, _due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")
    add(path, _due(2026, 10, 27, 10, 0), "m", "261027 - Beta", "Beta")
    add(path, _due(2026, 10, 27, 11, 0), "m", "261027 - Alpha", "Alpha")

    assert len(for_task(load(path), "261027 - Alpha")) == 2
    assert len(for_task(load(path), "261027 - Beta")) == 1


def test_remove_returns_true_for_existing_id_and_false_for_unknown(tmp_path):
    path = tmp_path / "reminders.json"
    reminder = add(path, _due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")

    assert remove(path, reminder.id) is True
    assert load(path) == []
    assert remove(path, reminder.id) is False
    assert remove(path, "unknown-id") is False


def test_pop_due_returns_due_ones_sorted_and_removes_them(tmp_path):
    path = tmp_path / "reminders.json"
    add(path, _due(2026, 10, 27, 9, 0), "late", "261027 - Alpha", "Alpha")
    add(path, _due(2026, 10, 27, 8, 0), "early", "261027 - Beta", "Beta")
    add(path, _due(2026, 10, 27, 10, 0), "later", "261027 - Gamma", "Gamma")

    now = _due(2026, 10, 27, 9, 0)
    due = pop_due(path, now)

    assert [r.message for r in due] == ["early", "late"]
    remaining = load(path)
    assert [r.message for r in remaining] == ["later"]


def test_pop_due_due_equals_now_counts_as_due(tmp_path):
    path = tmp_path / "reminders.json"
    add(path, _due(2026, 10, 27, 9, 0), "exact", "261027 - Alpha", "Alpha")
    add(path, _due(2026, 10, 27, 9, 1), "future", "261027 - Beta", "Beta")

    due = pop_due(path, _due(2026, 10, 27, 9, 0))
    assert [r.message for r in due] == ["exact"]
    assert [r.message for r in load(path)] == ["future"]


def test_pop_due_nothing_due_leaves_file_untouched(tmp_path):
    path = tmp_path / "reminders.json"
    add(path, _due(2026, 10, 27, 10, 0), "future", "261027 - Alpha", "Alpha")

    assert pop_due(path, _due(2026, 10, 27, 9, 0)) == []
    assert [r.message for r in load(path)] == ["future"]


def test_missing_file_gives_empty(tmp_path):
    assert load(tmp_path / "reminders.json") == []


def test_corrupted_file_is_renamed_to_bad_and_gives_empty(tmp_path):
    path = tmp_path / "reminders.json"
    path.write_text("{not json", encoding="utf-8")

    assert load(path) == []
    bad = tmp_path / "reminders.json.bad"
    assert bad.exists()
    assert not path.exists()


def test_existing_bad_is_replaced(tmp_path):
    path = tmp_path / "reminders.json"
    bad = tmp_path / "reminders.json.bad"
    bad.write_text("old", encoding="utf-8")
    path.write_text("{not json", encoding="utf-8")

    assert load(path) == []
    assert bad.read_text(encoding="utf-8") == "{not json"


def test_invalid_entries_skipped_valid_ones_kept(tmp_path):
    path = tmp_path / "reminders.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "reminders": [
                    {"id": "a", "due": "2026-10-27T09:00", "message": "m", "task": "t", "title": "T"},
                    {"id": "b", "due": "not-a-date", "message": "m", "task": "t", "title": "T"},
                    {"due": "2026-10-27T09:00", "message": "m", "task": "t", "title": "T"},
                    {"id": "c", "task": "t", "title": "T"},
                    "not an entry",
                ],
            }
        ),
        encoding="utf-8",
    )

    reminders = load(path)
    assert [r.id for r in reminders] == ["a"]


def test_top_level_that_is_not_a_reminders_object_is_renamed_to_bad(tmp_path):
    path = tmp_path / "reminders.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    assert load(path) == []
    assert (tmp_path / "reminders.json.bad").exists()
    assert not path.exists()


def test_write_error_leaves_no_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "reminders.json"

    def fail_replace(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        add(path, _due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")

    temps = [p for p in tmp_path.iterdir() if p.name.startswith(".reminders.json.")]
    assert temps == []


def test_atomic_write_leaves_no_temp_file(tmp_path):
    path = tmp_path / "reminders.json"
    add(path, _due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")

    temps = [p for p in tmp_path.iterdir() if p.name.startswith(".reminders.json.")]
    assert temps == []
    assert [r.message for r in load(path)] == ["m"]


def test_parent_directory_is_created(tmp_path):
    path = tmp_path / "sub" / "reminders.json"
    reminder = add(path, _due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")

    assert path.exists()
    assert load(path) == [reminder]


def test_reminders_path_is_next_to_config(tmp_path, monkeypatch):
    monkeypatch.setattr("mktsk.config.config_path", lambda: tmp_path / "config.json")
    assert reminders_path() == tmp_path / "reminders.json"
