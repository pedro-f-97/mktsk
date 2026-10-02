import datetime

import pytest
from freezegun import freeze_time

from mktsk.files import (
    append_date_section,
    create_folder,
    create_md_file,
    sign_md_file,
)
from mktsk.helpers import TaskError


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


@freeze_time("2026-09-22")
def test_sign_md_file_existing_space(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"

    file.write_text(" \n", encoding="utf-8")

    sign_md_file(file, "ThisTest")

    assert file.read_text(encoding="utf-8") == "# ThisTest\n\n## 22/09/2026\n\n"


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
