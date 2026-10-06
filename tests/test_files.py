import datetime

import pytest

from mktsk.files import (
    append_date_section,
    create_folder,
    create_md_file,
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


def test_append_date_section_borns_the_first_one(tmp_path):
    folder = tmp_path / "260922 - ThisTest"
    folder.mkdir()

    file = folder / "ThisTest.md"
    file.touch()

    assert append_date_section(file, datetime.date(2026, 9, 22)) is True

    # the date of a visit is a level 1 heading, the title is the file name
    assert file.read_text(encoding="utf-8") == "# 22/09/2026\n\n"


def test_append_date_section_on_a_blank_file(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(" \n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 22)) is True

    assert file.read_text(encoding="utf-8") == "# 22/09/2026\n\n"


def test_append_date_section(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
    )


def test_append_date_section_without_trailing_newline(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# 18/09/2026\n\nnotes", encoding="utf-8")

    append_date_section(file, datetime.date(2026, 9, 30))

    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
    )


def test_append_date_section_keeps_previous_sections(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# 18/09/2026\n\nfirst\n\n# 25/09/2026\n\nsecond\n",
        encoding="utf-8",
    )

    append_date_section(file, datetime.date(2026, 9, 30))

    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nfirst\n\n# 25/09/2026\n\nsecond\n\n# 30/09/2026\n\n"
    )


def test_append_date_section_existing_date(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# 30/09/2026\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "# 30/09/2026\n\nnotes\n"


def test_append_date_section_existing_date_on_a_file_that_starts_with_a_bom(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("\ufeff# 30/09/2026\n\nnotes\n", encoding="utf-8")

    # the section for today is the one the file already opens with
    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "\ufeff# 30/09/2026\n\nnotes\n"


def test_append_date_section_existing_date_with_stray_spacing(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("#  30/09/2026 \n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "#  30/09/2026 \n\nnotes\n"


def test_append_date_section_recognises_another_accepted_date_form(tmp_path):
    # the parser reads five forms, so a section written by hand in one of them is
    # the section of that date and is not written a second time
    file = tmp_path / "Foo.md"
    file.write_text("# 2026-09-30\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is False

    assert file.read_text(encoding="utf-8") == "# 2026-09-30\n\nnotes\n"


def test_append_date_section_ignores_a_date_in_body_text(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# 18/09/2026\n\nworked on 30/09/2026\n", encoding="utf-8"
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True


def test_append_date_section_ignores_a_date_in_a_code_block(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# 18/09/2026\n\n```\n# 30/09/2026\n```\n", encoding="utf-8"
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True


def test_append_date_section_ignores_a_second_level_heading(tmp_path):
    # a `##` is free for notes, so it dates nothing
    file = tmp_path / "Foo.md"
    file.write_text("# 18/09/2026\n\n## 30/09/2026\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True


def test_append_date_section_refuses_a_file_in_the_old_format(tmp_path):
    file = tmp_path / "Foo.md"
    content = "# Foo\n\n## 18/09/2026\n\nnotes\n"
    file.write_text(content, encoding="utf-8")

    with pytest.raises(TaskError, match=r"python -m mktsk\.migration"):
        append_date_section(file, datetime.date(2026, 9, 30))

    # nothing was written, so the migration can still convert the file
    assert file.read_text(encoding="utf-8") == content


def test_append_date_section_inserts_in_front_of_the_final_state_block(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\nnotes\n\n[mktsk:2026-10-02T09:40]: # "open"\n',
        encoding="utf-8",
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    # the block of state events is the end of the file, so the new section is
    # written in front of it and the event keeps its place
    assert file.read_text(encoding="utf-8") == (
        '# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n'
        '[mktsk:2026-10-02T09:40]: # "open"\n'
    )


def test_append_date_section_without_a_state_block(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("# 18/09/2026\n\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    # no block to sit in front of, so the section is appended as ever
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n# 30/09/2026\n\n"


def test_append_date_section_keeps_a_bom_in_front_of_everything(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text("\ufeff# 18/09/2026\n\nnotes\n", encoding="utf-8")

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    # the mark opens the file, never the section
    assert file.read_text(encoding="utf-8") == (
        "\ufeff# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
    )


def test_append_date_section_leaves_an_event_that_is_not_at_the_end(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        '# 18/09/2026\n\n[mktsk:2026-10-02T09:40]: # "open"\n\nnotes\n',
        encoding="utf-8",
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    # only the block at the end of the file is one, so this event is content
    # and the section goes after it
    assert file.read_text(encoding="utf-8") == (
        '# 18/09/2026\n\n[mktsk:2026-10-02T09:40]: # "open"\n\nnotes\n\n'
        "# 30/09/2026\n\n"
    )


def test_append_date_section_keeps_the_blank_line_before_a_block_of_two(tmp_path):
    file = tmp_path / "Foo.md"
    file.write_text(
        "# 18/09/2026\n\nnotes\n\n"
        '[mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-10-02T09:40]: # "in-progress"\n',
        encoding="utf-8",
    )

    assert append_date_section(file, datetime.date(2026, 9, 30)) is True

    # the whole final block is recognised, and the blank line that separates it
    # from the body is what the body still ends with
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n"
        '[mktsk:2026-09-18T10:02]: # "open"\n'
        '[mktsk:2026-10-02T09:40]: # "in-progress"\n'
    )
