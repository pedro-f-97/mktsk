"""How many attachments a task folder carries."""

from mktsk import listing


def test_a_folder_with_only_its_md_has_no_attachments(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    assert listing.attachment_count(tmp_path / "260918 - Foo") == 0


def test_every_other_direct_entry_counts(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    (folder / "archive.zip").write_text("", encoding="utf-8")
    (folder / "message.msg").write_text("", encoding="utf-8")

    assert listing.attachment_count(folder) == 2


def test_a_subfolder_counts_as_one_whatever_it_holds(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    subfolder = folder / "Attachments"
    subfolder.mkdir()
    (subfolder / "one.txt").write_text("", encoding="utf-8")
    (subfolder / "two.txt").write_text("", encoding="utf-8")

    assert listing.attachment_count(folder) == 1


def test_ignored_entries_are_left_out(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    for name in ("desktop.ini", "Thumbs.db", ".hidden", "~$x.docx"):
        (folder / name).write_text("", encoding="utf-8")

    assert listing.attachment_count(folder) == 0


def test_a_missing_folder_has_no_attachments(tmp_path):
    assert listing.attachment_count(tmp_path / "260918 - Missing") == 0


def test_an_archive_carries_no_attachments(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "260918 - Bar.zip").write_text("", encoding="utf-8")

    entries = {
        entry.title: entry
        for group in listing.find_task_groups(tmp_path)
        for entry in group.entries
    }

    assert entries["Bar"].attachments == 0
