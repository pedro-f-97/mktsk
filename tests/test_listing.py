import datetime
import zipfile
from pathlib import Path

from mktsk import listing
from mktsk.listing import (
    TaskEntry,
    find_task_folder,
    find_task_groups,
    list_subdirectories,
)
from mktsk.tasks import close_task


def test_find_task_groups_empty_directory(tmp_path):
    assert find_task_groups(tmp_path) == []


def test_find_task_groups_missing_directory(tmp_path):
    assert find_task_groups(tmp_path / "missing") == []


def test_find_task_groups_unpacks_date_title_and_file(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSocietyEverbind")

    groups = find_task_groups(tmp_path)

    assert len(groups) == 1
    assert groups[0].category is None
    assert groups[0].entries == [
        TaskEntry(
            datetime.date(2026, 9, 18),
            "FSocietyEverbind",
            file,
            datetime.date(2026, 9, 18),
            1,
            "open",
        )
    ]


def test_find_task_groups_root_task_has_no_category(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    groups = find_task_groups(tmp_path)

    assert [group.category for group in groups] == [None]


def test_find_task_groups_subdirectory_becomes_a_category(tmp_path, make_task):
    file = make_task(tmp_path / "Veritas", "260925", "FSociety")

    groups = find_task_groups(tmp_path)

    assert len(groups) == 1
    assert groups[0].category == tmp_path / "Veritas"
    assert groups[0].entries[0].file == file


def test_find_task_groups_comes_before_the_subdirectories(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")

    groups = find_task_groups(tmp_path)

    assert [group.category for group in groups] == [None, tmp_path / "Veritas"]


def test_find_task_groups_categories_are_alphabetical(tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    make_task(tmp_path / "Able", "260925", "Bar")
    make_task(tmp_path / "monad", "260925", "Baz")

    groups = find_task_groups(tmp_path)

    assert [
        group.category.name for group in groups if group.category is not None
    ] == ["Able", "monad", "Veritas"]


def test_find_task_groups_keeps_an_empty_category_in_the_alphabetical_order(
    tmp_path, make_task
):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    (tmp_path / "Able").mkdir()
    make_task(tmp_path / "monad", "260925", "Baz")

    groups = find_task_groups(tmp_path)

    names = []
    for group in groups:
        assert group.category is not None
        names.append(group.category.name)

    assert names == ["Able", "monad", "Veritas"]


def test_find_task_groups_sorts_newest_first(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260930", "Bar")
    make_task(tmp_path, "260925", "Baz")

    groups = find_task_groups(tmp_path)

    assert [entry.title for entry in groups[0].entries] == ["Bar", "Baz", "Foo"]


def test_find_task_groups_same_date_is_alphabetical(tmp_path, make_task):
    make_task(tmp_path, "260930", "Foo")
    make_task(tmp_path, "260930", "Bar")
    make_task(tmp_path, "260930", "Baz")

    groups = find_task_groups(tmp_path)

    assert [entry.title for entry in groups[0].entries] == ["Bar", "Baz", "Foo"]


def test_find_task_groups_stops_one_level_down(tmp_path, make_task):
    make_task(tmp_path / "SteelMountain" / "nested", "260924", "Everbind")

    groups = find_task_groups(tmp_path)

    # the category stands empty, and the task two levels down is not found
    assert len(groups) == 1
    assert groups[0].category == tmp_path / "SteelMountain"
    assert groups[0].entries == []


def test_find_task_groups_skips_task_folder_without_md(tmp_path):
    (tmp_path / "260918 - Foo").mkdir()

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_lists_a_subdirectory_without_tasks(tmp_path):
    (tmp_path / "SteelMountain").mkdir()

    groups = find_task_groups(tmp_path)

    assert len(groups) == 1
    assert groups[0].category == tmp_path / "SteelMountain"
    assert groups[0].entries == []


def test_find_task_groups_marks_a_category_of_only_closed_tasks_as_a_divider(
    tmp_path, make_task
):
    file = make_task(tmp_path / "Veritas", "260925", "Foo")
    close_task(file.parent, "Foo")

    groups = find_task_groups(tmp_path)

    # its tasks are gone into their archives, so what is left is the folder
    assert len(groups) == 1
    assert groups[0].category == tmp_path / "Veritas"
    assert groups[0].divider is True


def test_find_task_groups_keeps_a_category_with_an_open_task_off_the_divider(
    tmp_path, make_task
):
    make_task(tmp_path / "Veritas", "260925", "Open")
    closed = make_task(tmp_path / "Veritas", "260926", "Foo")
    close_task(closed.parent, "Foo")

    groups = find_task_groups(tmp_path)

    # a task that still stands keeps the folder with it
    assert groups[0].divider is False
    assert {entry.title for entry in groups[0].entries} == {"Open", "Foo"}


def test_find_task_groups_leaves_out_a_working_folder(tmp_path):
    (tmp_path / "_scratch").mkdir()

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_keeps_a_working_folder_off_the_divider(tmp_path, make_task):
    file = make_task(tmp_path / "_scratch", "260925", "Foo")
    close_task(file.parent, "Foo")

    groups = find_task_groups(tmp_path)

    # a working folder is no category of its own, so it stands nowhere
    assert groups[0].divider is False


def test_find_task_groups_leaves_out_a_dot_folder(tmp_path):
    (tmp_path / ".hidden").mkdir()

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_leaves_out_a_hidden_folder(tmp_path, monkeypatch):
    (tmp_path / "private").mkdir()
    # only Windows carries the attribute, so it is faked here
    monkeypatch.setattr(listing, "_has_hidden_attribute", lambda entry: True)

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_keeps_a_hidden_folder_off_the_divider(
    tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path / "private", "260925", "Foo")
    close_task(file.parent, "Foo")
    # only Windows carries the attribute, so it is faked here
    monkeypatch.setattr(listing, "_has_hidden_attribute", lambda entry: True)

    groups = find_task_groups(tmp_path)

    assert groups[0].divider is False


def test_find_task_groups_ignores_hidden_directories(tmp_path, make_task):
    make_task(tmp_path / ".hidden", "260902", "Foo")

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_ignores_files(tmp_path):
    (tmp_path / "a.md").touch()

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_invalid_date_prefix_is_a_subdirectory(tmp_path, make_task):
    folder = tmp_path / "999999 - ItsAlive"
    folder.mkdir()
    make_task(folder, "260925", "Foo")

    groups = find_task_groups(tmp_path)

    assert [group.category for group in groups] == [folder]
    assert [entry.title for entry in groups[0].entries] == ["Foo"]


def test_list_subdirectories_is_alphabetical(tmp_path):
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "able").mkdir()
    (tmp_path / "monad").mkdir()

    assert [path.name for path in list_subdirectories(tmp_path)] == [
        "able",
        "monad",
        "Veritas",
    ]


def test_list_subdirectories_leaves_out_task_folders_and_files(tmp_path):
    (tmp_path / "260918 - Foo").mkdir()
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "a.md").touch()

    assert [path.name for path in list_subdirectories(tmp_path)] == ["Veritas"]


def test_list_subdirectories_leaves_out_hidden_directories(tmp_path):
    (tmp_path / ".hidden").mkdir()

    assert list_subdirectories(tmp_path) == []


def test_list_subdirectories_stops_one_level_down(tmp_path):
    (tmp_path / "SteelMountain" / "nested").mkdir(parents=True)

    assert [path.name for path in list_subdirectories(tmp_path)] == ["SteelMountain"]


def test_list_subdirectories_unreadable_directory(tmp_path, monkeypatch):
    real_iterdir = Path.iterdir

    def guarded_iterdir(self):
        if self.name == "private":
            raise PermissionError
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    assert list_subdirectories(tmp_path / "private") == []


def test_find_task_groups_skips_unreadable_subdirectory(
    tmp_path, make_task, monkeypatch
):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    real_iterdir = Path.iterdir

    def guarded_iterdir(self):
        if self.name == "Veritas":
            raise PermissionError
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_lists_the_readable_categories(
    tmp_path, make_task, monkeypatch
):
    make_task(tmp_path, "260925", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    (tmp_path / "private").mkdir()
    real_iterdir = Path.iterdir

    def guarded_iterdir(self):
        if self.name == "private":
            raise PermissionError
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    # the category that cannot be read is left out, the rest is still listed
    groups = find_task_groups(tmp_path)

    assert [group.category for group in groups] == [None, tmp_path / "Veritas"]


def test_a_task_folder_with_a_reserved_title_is_still_visible(tmp_path):
    # not a task, so it is a plain folder the user can see, navigate to and
    # clear out, rather than one that is nowhere to be found
    (tmp_path / "261001 - CON").mkdir()

    assert list_subdirectories(tmp_path) == [tmp_path / "261001 - CON"]
    groups = find_task_groups(tmp_path)
    assert len(groups) == 1
    assert groups[0].category == tmp_path / "261001 - CON"
    assert groups[0].entries == []


# what a text file written by some editors starts with, and that is not text
BOM = "\ufeff"


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


def test_file_that_starts_with_a_bom_carries_its_interventions(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(f"{BOM}# 30/09/2026\n\nnotes\n", encoding="utf-8")

    entry = _entry(tmp_path)

    assert entry.last_activity == datetime.date(2026, 9, 30)
    assert entry.interventions == 1


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

    groups = find_task_groups(tmp_path)

    # the folder stands as a category of its own and holds no archive
    assert len(groups) == 1
    assert groups[0].category == tmp_path / "260918 - Foo.zip"
    assert groups[0].entries == []


def test_listing_finds_an_archive_in_a_category(tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260918", "Foo")
    close_task(tmp_path / "Veritas" / "260918 - Foo", "Foo")

    groups = find_task_groups(tmp_path)

    assert len(groups) == 1
    assert groups[0].category == tmp_path / "Veritas"
    assert groups[0].entries[0].state == "closed"


# what a text file written by some editors starts with, and that is not text


def test_entry_carries_the_state_of_the_file(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        "# 18/09/2026\n\n\n"
        '[mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-10-02T09:40]: # "waiting"\n',
        encoding="utf-8",
    )

    entry = _entry(tmp_path)

    # the last event in the file is the state the task is in
    assert entry.state == "waiting"


def test_entry_derives_the_state_without_events(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\n# 30/09/2026\n\n", encoding="utf-8")

    entry = _entry(tmp_path)

    # more than one section and no event: the task was worked on
    assert entry.state == "in-progress"


def test_entry_of_one_section_and_no_events_is_open(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")

    entry = _entry(tmp_path)

    assert entry.state == "open"


def test_unreadable_file_is_open(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "Foo")
    real_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self.name == "Foo.md":
            raise PermissionError
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    entry = _entry(tmp_path)

    # nothing can be read out of the file, so the task counts as open
    assert entry.state == "open"


def test_file_that_is_not_utf8_is_open(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_bytes(b"# 18/09/2026\n\ncaf\xe9\n")

    entry = _entry(tmp_path)

    assert entry.state == "open"


def test_old_format_file_is_open(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text(
        "# Foo\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8"
    )

    entry = _entry(tmp_path)

    # the old format is never read as the new one, so nothing says otherwise
    assert entry.state == "open"


def test_file_starting_with_a_bom_carries_its_state(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text(
        f'{BOM}# 18/09/2026\n\n\n[mktsk:2026-10-02T09:40]: # "in-progress"\n',
        encoding="utf-8",
    )

    entry = _entry(tmp_path)

    assert entry.state == "in-progress"


# How many attachments a task folder carries.


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


def test_list_attachments_leaves_the_task_md_out(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    (folder / "archive.zip").write_text("", encoding="utf-8")

    assert listing.list_attachments(folder) == ["archive.zip"]


def test_list_attachments_leaves_ignored_entries_out(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    for name in ("desktop.ini", "Thumbs.db", ".hidden", "~$x.docx"):
        (folder / name).write_text("", encoding="utf-8")

    assert listing.list_attachments(folder) == []


def test_a_subfolder_is_named_with_a_trailing_slash(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    (folder / "Attachments").mkdir()

    assert listing.list_attachments(folder) == ["Attachments/"]


def test_the_names_are_sorted_case_insensitively(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    for name in ("beta.txt", "Alpha.txt", "gamma.txt"):
        (folder / name).write_text("", encoding="utf-8")

    assert listing.list_attachments(folder) == ["Alpha.txt", "beta.txt", "gamma.txt"]


def test_a_missing_folder_lists_nothing(tmp_path):
    assert listing.list_attachments(tmp_path / "260918 - Missing") == []


def test_the_count_is_the_length_of_the_list(tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    (folder / "archive.zip").write_text("", encoding="utf-8")
    (folder / "Attachments").mkdir()
    for name in ("desktop.ini", ".hidden"):
        (folder / name).write_text("", encoding="utf-8")

    assert listing.attachment_count(folder) == len(listing.list_attachments(folder)) == 2


def test_find_task_folder_ignores_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Foo") == folder


def test_find_task_folder_ignores_the_case_of_the_title(tmp_path):
    # standardize_string lowers the capitals inside a title, so a folder renamed
    # by hand keeps ones the lookup would never produce. Copying its name into the
    # terminal has to reach the task, not create a second one
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Embalagemalteracaoformulario") == folder


def test_find_task_folder_excludes_a_folder(tmp_path):
    # how rename_task keeps a task from clashing with itself over the case alone
    folder = tmp_path / "260918 - AbCd"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Abcd") == folder
    assert find_task_folder(tmp_path, "Abcd", exclude=folder) is None


def test_find_task_folder_takes_the_most_recent_of_several(tmp_path):
    # a title is unique in a directory, but a folder copied by hand or restored
    # from a backup can leave two behind, and the newest is the one to resume
    for date in ("260918", "260925", "260930"):
        (tmp_path / f"{date} - Foo").mkdir()

    assert find_task_folder(tmp_path, "Foo") == tmp_path / "260930 - Foo"


def test_find_task_folder_takes_the_most_recent_whatever_the_iterdir_order(
    tmp_path, monkeypatch
):
    for date in ("260918", "260930"):
        (tmp_path / f"{date} - Foo").mkdir()

    folders = sorted(tmp_path.iterdir())
    monkeypatch.setattr(Path, "iterdir", lambda self: list(reversed(folders)))

    assert find_task_folder(tmp_path, "Foo") == tmp_path / "260930 - Foo"


def test_find_task_folder_ignores_subdirectories(tmp_path):
    (tmp_path / "Veritas" / "260925 - Foo").mkdir(parents=True)

    assert find_task_folder(tmp_path, "Foo") is None


def test_find_task_folder_ignores_hidden_prefix(tmp_path):
    (tmp_path / ".260918 - Foo").mkdir()

    assert find_task_folder(tmp_path, "Foo") is None


def test_find_task_folder_ignores_files(tmp_path):
    (tmp_path / "260918 - Foo").touch()

    assert find_task_folder(tmp_path, "Foo") is None


def test_find_task_folder_ignores_non_date_prefixes(tmp_path):
    for name in ("Memos - Foo", "26091 - Foo", "2609181 - Foo", "260918 - FooBar"):
        (tmp_path / name).mkdir()

    assert find_task_folder(tmp_path, "Foo") is None


def test_find_task_folder_ignores_invalid_calendar_date(tmp_path):
    (tmp_path / "999999 - Foo").mkdir()

    assert find_task_folder(tmp_path, "Foo") is None


def test_find_task_folder_missing_directory(tmp_path):
    assert find_task_folder(tmp_path / "missing", "Foo") is None
