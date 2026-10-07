import datetime
import zipfile

from mktsk.listing import find_task_groups
from mktsk.tasks import close_task


def test_listing_reads_an_archive(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        "# 18/09/2026\n\n# 30/09/2026\n\nnotes\n", encoding="utf-8"
    )
    close_task(tmp_path / "260918 - Foo", "Foo")

    groups = find_task_groups(tmp_path)

    entry = groups[0].entries[0]
    assert entry.title == "Foo"
    assert entry.date == datetime.date(2026, 9, 18)
    assert entry.state == "closed"
    assert entry.interventions == 2
    assert entry.last_activity == datetime.date(2026, 9, 30)
    assert entry.file == tmp_path / "260918 - Foo.zip"


def test_listing_sorts_an_archive_with_the_folders(tmp_path, make_task):
    closed = make_task(tmp_path, "260918", "Foo")
    closed.write_text("# 18/09/2026\n\n# 01/10/2026\n\n", encoding="utf-8")
    close_task(tmp_path / "260918 - Foo", "Foo")
    make_task(tmp_path, "260919", "Bar")

    entries = find_task_groups(tmp_path)[0].entries

    # the archive sits where its last activity puts it, among the folders
    assert [entry.title for entry in entries] == ["Foo", "Bar"]
    assert [entry.state for entry in entries] == ["closed", "open"]


def test_listing_survives_a_zip_that_cannot_be_read(tmp_path):
    (tmp_path / "260918 - Foo.zip").write_bytes(b"not a zip")

    entries = find_task_groups(tmp_path)[0].entries

    entry = entries[0]
    assert entry.state == "closed"
    assert entry.interventions == 0
    assert entry.last_activity == datetime.date(2026, 9, 18)


def test_listing_an_archive_without_its_md(tmp_path):
    with zipfile.ZipFile(tmp_path / "260918 - Foo.zip", "w") as archive:
        archive.writestr("other.txt", "content")

    entries = find_task_groups(tmp_path)[0].entries

    entry = entries[0]
    assert entry.state == "closed"
    assert entry.interventions == 0
    assert entry.last_activity == datetime.date(2026, 9, 18)


def test_listing_an_archive_holding_an_old_format_file(tmp_path):
    with zipfile.ZipFile(tmp_path / "260918 - Foo.zip", "w") as archive:
        archive.writestr("260918 - Foo/Foo.md", "# Foo\n\n## 18/09/2026\n\nnotes\n")

    entries = find_task_groups(tmp_path)[0].entries

    # an old file is never read as the new one, the same as in a folder
    entry = entries[0]
    assert entry.state == "closed"
    assert entry.interventions == 0
    assert entry.last_activity == datetime.date(2026, 9, 18)


def test_listing_an_archive_whose_file_carries_no_intervention(tmp_path):
    with zipfile.ZipFile(tmp_path / "260918 - Foo.zip", "w") as archive:
        archive.writestr("260918 - Foo/Foo.md", "just notes\n")

    entries = find_task_groups(tmp_path)[0].entries

    entry = entries[0]
    assert entry.state == "closed"
    assert entry.interventions == 0
    assert entry.last_activity == datetime.date(2026, 9, 18)


def test_listing_ignores_a_directory_that_looks_like_an_archive(tmp_path):
    (tmp_path / "260918 - Foo.zip").mkdir()

    assert find_task_groups(tmp_path) == []


def test_listing_finds_an_archive_in_a_category(tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260918", "Foo")
    close_task(tmp_path / "Veritas" / "260918 - Foo", "Foo")

    groups = find_task_groups(tmp_path)

    assert len(groups) == 1
    assert groups[0].category == tmp_path / "Veritas"
    assert groups[0].entries[0].state == "closed"
