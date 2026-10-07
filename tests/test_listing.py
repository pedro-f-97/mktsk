import datetime
from pathlib import Path

from mktsk.listing import (
    TaskEntry,
    find_task_groups,
    list_subdirectories,
)


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

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_skips_task_folder_without_md(tmp_path):
    (tmp_path / "260918 - Foo").mkdir()

    assert find_task_groups(tmp_path) == []


def test_find_task_groups_skips_subdirectory_without_tasks(tmp_path):
    (tmp_path / "SteelMountain").mkdir()

    assert find_task_groups(tmp_path) == []


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
    # not a task and not a category, so it is a plain folder the user can see,
    # navigate to and clear out, rather than one that is nowhere to be found
    (tmp_path / "261001 - CON").mkdir()

    assert list_subdirectories(tmp_path) == [tmp_path / "261001 - CON"]
    assert find_task_groups(tmp_path) == []
