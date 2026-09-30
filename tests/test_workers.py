import datetime

import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.workers import (
    append_date_section,
    build_folder_name,
    create_folder,
    create_md_file,
    find_task_folder,
    is_task_folder,
    open_or_create_task,
    sign_md_file,
    standardize_string,
)


def test_standardize_string():
    test_string = "Sigur Rós"
    standardized_string = standardize_string(test_string)

    assert standardized_string == "SigurRos"

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

def test_sign_md_file_existing_untouched(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    file.write_text("# This is some other text\n", encoding="utf-8")

    sign_md_file(file, "260922 - ThisTest")

    assert file.read_text(encoding="utf-8") == "# This is some other text\n"

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