import datetime
from pathlib import Path

import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.workers import (
    TaskEntry,
    append_date_section,
    build_folder_name,
    create_category,
    create_folder,
    create_md_file,
    find_task_folder,
    find_task_groups,
    is_task_folder,
    list_subdirectories,
    open_or_create_task,
    rename_task,
    resume_task,
    sign_md_file,
    standardize_string,
)


def test_standardize_string():
    test_string = "Sigur Rós"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "SigurRos"

@pytest.mark.parametrize("apostrophe", ["'", "\u2019"])
def test_standardize_string_keeps_a_contraction_together(apostrophe):
    standardized_string = standardize_string(f"It{apostrophe}s Alive!")

    # the apostrophe joins the word, it does not make "s" start one
    assert standardized_string == "ItsAlive"

def test_standardize_string_spacing():
    test_string = "bJÖrk_naÏve-fAçAde!!"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "BjorkNaiveFacade"

def test_build_folder_name():
    name = "CoolFolder"
    prefix = "260921"
    assert build_folder_name(name, prefix) == "260921 - CoolFolder"

def test_build_folder_name_default_prefix():
    with freeze_time("2026-09-21"):
        assert build_folder_name("FrozenFolder") == "260921 - FrozenFolder"

def test_create_folder(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    created_folder = (folder / "260921 - TargetFolder")

    assert created_folder == create_folder(folder, "260921 - TargetFolder")
    assert created_folder.exists()

def test_create_folder_create_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    create_folder(target, "child")
    assert (target / "child").is_dir()

def test_create_folder_existing(tmp_path):
    (tmp_path / "exists").mkdir()
    create_folder(tmp_path, "exists")
    assert (tmp_path / "exists").is_dir()

def test_create_folder_error(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()

    with pytest.raises(TaskError):
        create_folder(folder, "/etc")

def test_create_md_file(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    name = "EmDiFile"
    created = folder / f"{name}.md"

    assert create_md_file(folder, name) == created
    assert created.exists()

def test_create_md_file_path_error(tmp_path):
    folder = (tmp_path / "my_folder")
    folder.mkdir()
    name = "/etc"

    with pytest.raises(TaskError):
        create_md_file(folder, name)

@pytest.mark.parametrize("name", ["CON", "com1.log"])
def test_create_md_file_reserved_name(tmp_path, name):
    folder = (tmp_path / "my_folder")
    folder.mkdir()

    # a task folder copied by hand can carry a title Windows reserves, and the
    # .md of that title is as reserved as the folder name
    with pytest.raises(TaskError):
        create_md_file(folder, name)

    assert list(folder.iterdir()) == []

def test_create_folder_takes_a_reserved_name(tmp_path):
    # the date prefix keeps a task folder name out of the reserved set, so
    # create_folder is not the place the rule belongs and does not check it
    created = create_folder(tmp_path, "CON")

    assert created.exists()

@freeze_time("2026-09-22")
def test_sign_md_file(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    sign_md_file(file, "ThisTest")

    assert file.read_text(encoding="utf-8") == "# ThisTest\n\n## 22/09/2026\n\n"

@freeze_time("2026-09-22")
def test_sign_md_file_existing_ok(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    # a different date, so a rewrite would be visible in the assertion
    file.write_text("# ThisTest\n\n## 20/09/2026\n\n", encoding="utf-8")

    sign_md_file(file, "ThisTest")

    assert file.read_text(encoding="utf-8") == "# ThisTest\n\n## 20/09/2026\n\n"

def test_sign_md_file_completes_foreign_content(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    # a folder copied by hand, so the heading names a different task
    file.write_text("# This is some other text\n", encoding="utf-8")

    assert sign_md_file(file, "ThisTest") is False

    assert (
        file.read_text(encoding="utf-8")
        == "# ThisTest\n\n# This is some other text\n"
    )

def test_sign_md_file_completes_content_without_a_heading(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.write_text("some content\n", encoding="utf-8")

    assert sign_md_file(file, "ThisTest") is False

    assert file.read_text(encoding="utf-8") == "# ThisTest\n\nsome content\n"

def test_sign_md_file_leaves_a_matching_heading_alone(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    original = "# ThisTest\n\n## 20/09/2026\n\nnotes\n"
    file.write_text(original, encoding="utf-8")

    assert sign_md_file(file, "ThisTest") is False

    assert file.read_text(encoding="utf-8") == original

@freeze_time("2026-09-30")
def test_open_or_create_task_signs_foreign_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# AnotherTask\n\nsome content\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert (
        result.file.read_text(encoding="utf-8")
        == "# Foo\n\n# AnotherTask\n\nsome content\n\n## 30/09/2026\n\n"
    )

@freeze_time("2026-09-22")
def test_sign_md_file_existing_space(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"

    file.write_text(" \n", encoding="utf-8")

    sign_md_file(file, "ThisTest")

    assert file.read_text(encoding="utf-8") == "# ThisTest\n\n## 22/09/2026\n\n"

def test_is_task_folder():
    assert is_task_folder("260930 - ItsAlive")
    assert is_task_folder("260710 - BuildSearchResults")
    assert is_task_folder("260709 - Everbind")

def test_is_task_folder_numeric_title():
    assert is_task_folder("260930 - 2026")

def test_is_task_folder_invalid_calendar_date():
    assert not is_task_folder("999999 - ItsAlive")
    assert not is_task_folder("261301 - ItsAlive")
    assert not is_task_folder("260230 - ItsAlive")
    assert not is_task_folder("268231 - ItsAlive")

def test_is_task_folder_bad_date_prefix_length():
    assert not is_task_folder("26093 - ItsAlive")
    assert not is_task_folder("2609301 - ItsAlive")
    assert not is_task_folder("abcdef - ItsAlive")

def test_is_task_folder_missing_separator_or_title():
    assert not is_task_folder("260930ItsAlive")
    assert not is_task_folder("260930 - ")
    assert not is_task_folder("260930- ItsAlive")
    assert not is_task_folder("ItsAlive")
    assert not is_task_folder("")

def test_is_task_folder_title_not_standardized():
    assert not is_task_folder("260930 - Blá")
    assert not is_task_folder("260930 - Its Alive")
    assert not is_task_folder("260930 - itsAlive")
    assert not is_task_folder("260930 - Its_Alive")
    assert not is_task_folder("260930 - ItsAlive - Part2")
    assert not is_task_folder("260930 - ItsAlive ")

def test_find_task_folder_ignores_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Foo") == folder

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

def test_append_date_section(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# Foo\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    assert file.read_text(encoding="utf-8") == (
        "# Foo\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )

def test_append_date_section_without_trailing_newline(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# Foo\n\n## 18/09/2026\n\nnotes", encoding="utf-8")

    append_date_section(file, datetime.date(2026, 9, 30))

    assert file.read_text(encoding="utf-8") == (
        "# Foo\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )

def test_append_date_section_keeps_previous_sections(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# Foo\n\n## 18/09/2026\n\nfirst\n\n## 25/09/2026\n\nsecond\n",
        encoding="utf-8",
    )

    append_date_section(file, datetime.date(2026, 9, 30))

    assert file.read_text(encoding="utf-8") == (
        "# Foo\n\n## 18/09/2026\n\nfirst\n\n"
        "## 25/09/2026\n\nsecond\n\n## 30/09/2026\n\n"
    )

def test_append_date_section_existing_date(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# Foo\n\n## 30/09/2026\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "# Foo\n\n## 30/09/2026\n\nnotes\n"

def test_append_date_section_existing_date_with_stray_spacing(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# Foo\n\n##  30/09/2026 \n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "# Foo\n\n##  30/09/2026 \n\nnotes\n"

def test_append_date_section_ignores_date_in_body_text(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# Foo\n\n## 18/09/2026\n\nworked on 30/09/2026\n", encoding="utf-8"
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

def test_append_date_section_ignores_other_heading_levels(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# Foo\n\n# 30/09/2026\n\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

@freeze_time("2026-09-30")
def test_open_or_create_task_creates(tmp_path):
    result = open_or_create_task(tmp_path, "Its Alive!")

    file = tmp_path / "260930 - ItsAlive" / "ItsAlive.md"

    assert result.file == file
    assert result.message == "Created: 260930 - ItsAlive"
    assert file.read_text(encoding="utf-8") == "# ItsAlive\n\n## 30/09/2026\n\n"

@freeze_time("2026-09-30")
def test_open_or_create_task_finds_existing_by_title(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# Foo\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == file
    assert result.message == "Opened: 260918 - Foo (added ## 30/09/2026)"
    assert file.read_text(encoding="utf-8") == (
        "# Foo\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )
    assert list(tmp_path.iterdir()) == [folder]

@freeze_time("2026-09-30")
def test_open_or_create_task_ignores_task_in_subdirectory(tmp_path):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260925 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n\n## 25/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"
    assert result.message == "Created: 260930 - Foo"

@freeze_time("2026-09-30")
def test_open_or_create_task_creates_when_date_prefix_is_not_a_date(tmp_path):
    folder = tmp_path / "999999 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n\n## 30/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"
    assert result.message == "Created: 260930 - Foo"

@freeze_time("2026-09-30")
def test_open_or_create_task_resumes_a_task_with_a_valid_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n\n## 18/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == folder / "Foo.md"
    assert result.message == "Opened: 260918 - Foo (added ## 30/09/2026)"

@freeze_time("2026-09-30")
def test_open_or_create_task_resumes_the_most_recent_of_several(tmp_path):
    for date in ("260918", "260930"):
        folder = tmp_path / f"{date} - Foo"
        folder.mkdir()
        (folder / "Foo.md").write_text(f"# Foo\n\n## {date}\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"

@freeze_time("2026-09-30")
def test_open_or_create_task_same_day_only_once(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# Foo\n\n## 18/09/2026\n\n", encoding="utf-8")

    first = open_or_create_task(tmp_path, "Foo")
    second = open_or_create_task(tmp_path, "Foo")

    assert first.message == "Opened: 260918 - Foo (added ## 30/09/2026)"
    assert second.message == "Opened: 260918 - Foo (## 30/09/2026 already there)"
    assert file.read_text(encoding="utf-8").count("## 30/09/2026") == 1

@freeze_time("2026-09-30")
def test_open_or_create_task_signs_missing_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == "Opened: 260918 - Foo"
    assert result.file.read_text(encoding="utf-8") == "# Foo\n\n## 30/09/2026\n\n"

@freeze_time("2026-09-30")
def test_open_or_create_task_signs_blank_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text(" \n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file.read_text(encoding="utf-8") == "# Foo\n\n## 30/09/2026\n\n"

def test_open_or_create_task_empty_title(tmp_path):
    with pytest.raises(TaskError):
        open_or_create_task(tmp_path, "   ")

    assert list(tmp_path.iterdir()) == []

def test_open_or_create_task_invalid_title(tmp_path):
    with pytest.raises(TaskError):
        open_or_create_task(tmp_path, "!!!")

    assert list(tmp_path.iterdir()) == []

def test_open_or_create_task_reserved_name(tmp_path):
    with pytest.raises(TaskError):
        open_or_create_task(tmp_path, "con")

    assert list(tmp_path.iterdir()) == []
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
        TaskEntry(datetime.date(2026, 9, 18), "FSocietyEverbind", file)
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


@freeze_time("2026-09-30")
def test_resume_task_uses_the_given_folder(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")
    folder = tmp_path / "260918 - FSociety"

    result = resume_task(folder, "FSociety")

    assert result.file == folder / "FSociety.md"
    assert "## 30/09/2026" in result.file.read_text(encoding="utf-8")

@freeze_time("2026-09-30")
def test_resume_task_ignores_the_current_directory(tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260918", "FSociety")
    folder = tmp_path / "Veritas" / "260918 - FSociety"
    elsewhere = tmp_path / "SteelMountain"
    elsewhere.mkdir()

    result = resume_task(folder, "FSociety")

    assert result.file == folder / "FSociety.md"
    assert list(elsewhere.iterdir()) == []


@freeze_time("2026-09-30")
def test_resume_task_refuses_a_reserved_title(tmp_path):
    # a folder the lookup would never have created, so a copy by hand or a
    # restore from a backup, which is what the GUI Resume button can be given
    folder = tmp_path / "260918 - CON"
    folder.mkdir()

    with pytest.raises(TaskError):
        resume_task(folder, "CON")

    assert list(folder.iterdir()) == []


@freeze_time("2026-09-30")
def test_rename_task_keeps_the_date_and_rewrites_the_heading(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("# FSociety\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "F Society Everbind")

    assert result.file == tmp_path / "260918 - FSocietyEverbind" / "FSocietyEverbind.md"
    assert result.message == "Renamed: 260918 - FSocietyEverbind"

def test_rename_task_leaves_the_rest_of_the_file_alone(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text(
        "# FSociety\n\n## 18/09/2026\n\n# FSociety\n\nbody\n", encoding="utf-8"
    )

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == (
        "# Everbind\n\n## 18/09/2026\n\n# FSociety\n\nbody\n"
    )

def test_rename_task_leaves_a_heading_it_does_not_recognise(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("notes first\n# FSociety\n", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == "notes first\n# FSociety\n"

def test_rename_task_ignores_a_heading_with_stray_spacing(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("  # FSociety  \n\nbody\n", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == "# Everbind\n\nbody\n"

def test_rename_task_to_the_title_it_already_has(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")
    folder = tmp_path / "260918 - FSociety"

    result = rename_task(folder, "FSociety", "F Society")

    assert result.file == folder / "FSociety.md"
    assert result.message == "Renamed: 260918 - FSociety"

def test_rename_task_rejects_an_empty_title(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")

    with pytest.raises(TaskError, match="invalid task description"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "!!!")

def test_rename_task_rejects_a_blank_title(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")

    with pytest.raises(TaskError, match="invalid task description"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "   ")

def test_rename_task_rejects_a_reserved_name(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")

    with pytest.raises(TaskError, match="reserved name"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "con")

def test_rename_task_rejects_a_task_that_is_already_there(tmp_path, make_task):
    make_task(tmp_path, "260917", "FSocietyEverbind")
    file = make_task(tmp_path, "260918", "FSociety")

    with pytest.raises(TaskError, match="already a task here"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "F Society Everbind")

    assert file.read_text(encoding="utf-8") == "# FSociety\n"
    assert (tmp_path / "260917 - FSocietyEverbind").is_dir()

def test_rename_task_rejects_a_title_of_another_date(tmp_path, make_task):
    # a title is unique in a directory, whichever date the task it clashes with
    # carries, so renaming must not be the way to end up with two of one title
    other = make_task(tmp_path, "260930", "FSociety")
    file = make_task(tmp_path, "260918", "Veritas")

    with pytest.raises(TaskError, match="already a task here"):
        rename_task(tmp_path / "260918 - Veritas", "Veritas", "F Society")

    assert file.read_text(encoding="utf-8") == "# Veritas\n"
    assert other.read_text(encoding="utf-8") == "# FSociety\n"
    assert not (tmp_path / "260918 - FSociety").exists()

def test_rename_task_rejects_a_folder_without_markdown(tmp_path):
    (tmp_path / "260918 - FSociety").mkdir()

    with pytest.raises(TaskError, match="no Markdown file"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

def test_rename_task_skips_blank_lines_before_the_heading(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("\n\n# FSociety\n\nbody\n", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == "\n\n# Everbind\n\nbody\n"

def test_rename_task_leaves_a_file_without_any_content(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == ""

def test_rename_task_puts_the_file_back_when_the_folder_cannot_move(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "FSociety")
    original = Path.rename

    def rename(self, target):
        if self.is_dir():
            raise OSError("test error")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", rename)

    with pytest.raises(OSError, match="test error"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    # the folder did not move, so the file must not be left carrying a new name
    assert (tmp_path / "260918 - FSociety" / "FSociety.md").is_file()
    assert not (tmp_path / "260918 - FSociety" / "Everbind.md").exists()
    assert not (tmp_path / "260918 - Everbind").exists()

def test_rename_task_puts_everything_back_when_the_heading_cannot_be_written(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "FSociety")
    original = Path.write_text

    def write_text(self, data, **kwargs):
        if data.startswith("# Everbind"):
            raise OSError("test error")
        return original(self, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)

    with pytest.raises(OSError, match="test error"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    # the heading could not be written, so the names went back too
    folder = tmp_path / "260918 - FSociety"
    assert sorted(entry.name for entry in folder.iterdir()) == ["FSociety.md"]
    assert (folder / "FSociety.md").read_text(encoding="utf-8") == "# FSociety\n"
    assert not (tmp_path / "260918 - Everbind").exists()

def test_rename_task_leaves_the_file_alone_when_it_cannot_be_put_back(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "FSociety")
    original = Path.rename

    def rename(self, target):
        if self.name == "260918 - FSociety":
            raise OSError("test error")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", rename)

    # a rollback that fails is reported rather than swallowed
    with pytest.raises(OSError, match="test error"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

def test_create_category_creates_the_folder(tmp_path):
    category = create_category(tmp_path, "Veritas")

    assert category == tmp_path / "Veritas"
    assert category.is_dir()

def test_create_category_strips_the_accents(tmp_path):
    assert create_category(tmp_path, "Produção") == tmp_path / "Producao"
    assert (tmp_path / "Producao").is_dir()

def test_create_category_keeps_the_case_and_the_spaces(tmp_path):
    assert create_category(tmp_path, "my tasks") == tmp_path / "my tasks"

def test_create_category_returns_the_folder_that_is_already_there(tmp_path):
    existing = tmp_path / "Veritas"
    existing.mkdir()

    assert create_category(tmp_path, "Veritas") == existing

def test_create_category_leaves_the_folder_that_is_already_there_alone(tmp_path):
    existing = tmp_path / "Veritas"
    existing.mkdir()
    (existing / "notes.md").write_text("notes\n", encoding="utf-8")

    create_category(tmp_path, "Veritas")

    assert (existing / "notes.md").read_text(encoding="utf-8") == "notes\n"

def test_create_category_rejects_an_empty_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "")

def test_create_category_rejects_a_blank_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "   ")

def test_create_category_rejects_a_name_with_a_separator(tmp_path):
    with pytest.raises(TaskError, match="single path component"):
        create_category(tmp_path, "a/b")

def test_create_category_rejects_a_reserved_name(tmp_path):
    with pytest.raises(TaskError, match="reserved name"):
        create_category(tmp_path, "con")

@pytest.mark.parametrize(
    "name",
    ["foo:bar", "foo?", "foo*", "foo|", "foo.", "foo ", r"C:\foo", "con.txt"],
)
def test_create_category_reports_a_name_windows_would_refuse(tmp_path, name):
    # a domain error, not the raw OSError of whichever machine we are on
    with pytest.raises(TaskError):
        create_category(tmp_path, name)

    assert list(tmp_path.iterdir()) == []

def test_create_category_rejects_a_hidden_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, ".hidden")

def test_create_category_rejects_a_task_folder_name(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "260918 - Foo")

def test_create_category_rejects_a_name_it_cannot_make_ascii(tmp_path):
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "日本語")

def test_create_category_rejects_a_task_folder_name_with_accents(tmp_path):
    # folding the accents is what turns this into a valid task folder name
    with pytest.raises(TaskError, match="invalid category name"):
        create_category(tmp_path, "260918 - FooÇo")

def test_create_category_is_listed_as_a_category(tmp_path):
    create_category(tmp_path, "Veritas")

    assert list_subdirectories(tmp_path) == [tmp_path / "Veritas"]
