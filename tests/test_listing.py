import datetime
from pathlib import Path

from mktsk import listing
from mktsk.listing import (
    TaskEntry,
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
