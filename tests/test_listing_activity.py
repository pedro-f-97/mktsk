import datetime
from pathlib import Path

from mktsk.listing import find_task_groups


def _entry(tmp_path):
    """The single task entry of a directory, which the tests below check."""
    return find_task_groups(tmp_path)[0].entries[0]


def test_entry_carries_the_last_activity_and_the_interventions(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n", encoding="utf-8")

    entry = _entry(tmp_path)

    assert entry.last_activity == datetime.date(2026, 9, 30)
    assert entry.interventions == 2


def test_entry_keeps_the_folder_date(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 30/09/2026\n\n", encoding="utf-8")

    entry = _entry(tmp_path)

    assert entry.date == datetime.date(2026, 9, 18)


def test_file_without_interventions_falls_back_to_the_folder_date(tmp_path):
    (tmp_path / "260918 - Foo").mkdir()
    (tmp_path / "260918 - Foo" / "Foo.md").write_text("just notes\n", encoding="utf-8")

    entry = _entry(tmp_path)

    assert entry.last_activity == datetime.date(2026, 9, 18)
    assert entry.interventions == 0


def test_old_format_file_falls_back_to_the_folder_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text(
        "# Foo\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8"
    )

    entry = _entry(tmp_path)

    # the old format dates its visits with a level 2 heading, so the parser reads
    # no intervention at all and the folder date stands in
    assert entry.last_activity == datetime.date(2026, 9, 18)
    assert entry.interventions == 0


def test_old_format_file_with_a_dated_heading_falls_back_to_the_folder_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    # a file part way through the conversion: a level 2 heading from the old
    # format, and a level 1 one someone left in the body
    (folder / "Foo.md").write_text(
        "# Foo\n\n## 18/09/2026\n\nnotes\n\n# 30/09/2026\n\nquoted changelog\n",
        encoding="utf-8",
    )

    entry = _entry(tmp_path)

    # the dated heading is content of a file mktsk refuses to touch, not a visit
    assert entry.last_activity == datetime.date(2026, 9, 18)
    assert entry.interventions == 0


def test_unreadable_file_does_not_bring_the_listing_down(
    tmp_path, make_task, monkeypatch
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260925", "Bar")
    real_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self.name == "Foo.md":
            raise PermissionError
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    entries = find_task_groups(tmp_path)[0].entries

    # the task that cannot be read is still there, and so is the one beside it
    assert [entry.title for entry in entries] == ["Bar", "Foo"]
    assert entries[1].last_activity == datetime.date(2026, 9, 18)
    assert entries[1].interventions == 0


def test_file_that_is_not_utf8_keeps_the_task_in_the_listing(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_bytes(b"# 18/09/2026\n\ncaf\xe9\n")

    entry = _entry(tmp_path)

    # a file saved by something other than mktsk is still a task file
    assert entry.last_activity == datetime.date(2026, 9, 18)
    assert entry.interventions == 0


def test_task_resumed_later_moves_up_the_order(tmp_path, make_task):
    resumed = make_task(tmp_path, "260918", "Foo")
    resumed.write_text("# 18/09/2026\n\n# 05/10/2026\n\n", encoding="utf-8")
    make_task(tmp_path, "260930", "Bar")

    entries = find_task_groups(tmp_path)[0].entries

    # Foo was worked on after Bar was created, so it comes first
    assert [entry.title for entry in entries] == ["Foo", "Bar"]


def test_same_last_activity_is_alphabetical(tmp_path, make_task):
    resumed = make_task(tmp_path, "260918", "Foo")
    resumed.write_text("# 18/09/2026\n\n# 05/10/2026\n\n", encoding="utf-8")
    fresh = make_task(tmp_path, "260925", "Bar")
    fresh.write_text("# 25/09/2026\n\n# 05/10/2026\n\n", encoding="utf-8")

    entries = find_task_groups(tmp_path)[0].entries

    assert [entry.title for entry in entries] == ["Bar", "Foo"]
