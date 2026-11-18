import datetime
from pathlib import Path

import pytest
from freezegun import freeze_time

from mktsk import reminders
from mktsk.helpers import TaskError
from mktsk.tasks import (
    close_task,
    move_task,
    open_or_create_task,
    rename_task,
    resume_task,
)


@freeze_time("2026-09-30")
def test_open_or_create_task_appends_to_foreign_content(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# AnotherTask\n\nsome content\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert (
        result.file.read_text(encoding="utf-8")
        == "# AnotherTask\n\nsome content\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_creates(tmp_path):
    result = open_or_create_task(tmp_path, "Its Alive!")

    file = tmp_path / "260930 - ItsAlive" / "ItsAlive.md"

    assert result.file == file
    assert result.message == "Created: 260930 - ItsAlive (state: open)"
    # the file is born with the section that dates this visit, and no title;
    # two blank lines stand between the heading and the open event, so a note
    # typed on the first one never runs into the block
    assert file.read_text(encoding="utf-8") == (
        '# 30/09/2026\n\n\n[mktsk:2026-09-30T00:00]: # "open"\n'
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_finds_existing_by_title(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == file
    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )
    assert list(tmp_path.iterdir()) == [folder]


@freeze_time("2026-09-30")
def test_open_or_create_task_ignores_task_in_subdirectory(tmp_path):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260925 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# 25/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"
    assert result.message == "Created: 260930 - Foo (state: open)"


@freeze_time("2026-09-30")
def test_open_or_create_task_creates_when_date_prefix_is_not_a_date(tmp_path):
    folder = tmp_path / "999999 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# 30/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"
    assert result.message == "Created: 260930 - Foo (state: open)"


@freeze_time("2026-09-30")
def test_open_or_create_task_resumes_a_task_with_a_valid_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# 18/09/2026\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == folder / "Foo.md"
    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_resumes_the_most_recent_of_several(tmp_path):
    for prefix, date in (("260918", "18/09/2026"), ("260930", "30/09/2026")):
        folder = tmp_path / f"{prefix} - Foo"
        folder.mkdir()
        (folder / "Foo.md").write_text(f"# {date}\n\n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.file == tmp_path / "260930 - Foo" / "Foo.md"


@freeze_time("2026-09-30")
def test_open_or_create_task_same_day_only_once(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    file.write_text("# 18/09/2026\n\n", encoding="utf-8")

    first = open_or_create_task(tmp_path, "Foo")
    second = open_or_create_task(tmp_path, "Foo")

    assert first.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert second.message == "Opened: 260918 - Foo (# 30/09/2026 already there)"
    assert file.read_text(encoding="utf-8").count("# 30/09/2026") == 1


@freeze_time("2026-09-30")
def test_open_or_create_task_dates_a_missing_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert result.file.read_text(encoding="utf-8") == (
        '# 30/09/2026\n\n\n[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_dates_a_blank_md(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text(" \n", encoding="utf-8")

    result = open_or_create_task(tmp_path, "Foo")

    assert result.message == (
        "Opened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert result.file.read_text(encoding="utf-8") == (
        '# 30/09/2026\n\n\n[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_refuses_a_file_in_the_old_format(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    file = folder / "Foo.md"
    content = "# Foo\n\n## 18/09/2026\n\nnotes\n"
    file.write_text(content, encoding="utf-8")

    with pytest.raises(TaskError, match=r"is in the old format and was not read"):
        open_or_create_task(tmp_path, "Foo")

    # the file is left as it was
    assert file.read_text(encoding="utf-8") == content


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


@freeze_time("2026-09-30")
def test_open_or_create_task_reopens_a_task_that_is_archived(tmp_path, make_task):
    with freeze_time("2026-09-18"):
        file = make_task(tmp_path, "260918", "Foo")
        close_task(file.parent, "Foo")

    # the title is unique whether the task stands as a folder or as an
    # archive, and an archive with no folder beside it is the task to reopen
    result = open_or_create_task(tmp_path, "foo")

    assert result.message == (
        "Reopened: 260918 - Foo (added # 30/09/2026) (state: in-progress)"
    )
    assert (tmp_path / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()


@freeze_time("2026-09-30")
def test_resume_task_uses_the_given_folder(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")
    folder = tmp_path / "260918 - FSociety"

    result = resume_task(folder, "FSociety")

    assert result.file == folder / "FSociety.md"
    assert "# 30/09/2026" in result.file.read_text(encoding="utf-8")


@freeze_time("2026-09-30")
def test_resume_task_keeps_the_caps_the_folder_carries(tmp_path):
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()
    original = folder / "EmbalagemAlteracaoFormulario.md"
    original.write_text("# 18/09/2026\n\nnotas\n", encoding="utf-8")

    result = resume_task(folder, "Embalagemalteracaoformulario")

    # the .md is the one that was there, and no other file was created
    assert [path.name for path in folder.iterdir()] == [original.name]
    assert result.file == original
    assert result.file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotas\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )


@freeze_time("2026-09-30")
def test_resume_task_refuses_a_file_in_the_old_format(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    content = "# FSociety\n\n## 18/09/2026\n\nnotas\n"
    file.write_text(content, encoding="utf-8")

    with pytest.raises(TaskError, match=r"is in the old format and was not read"):
        resume_task(tmp_path / "260918 - FSociety", "FSociety")

    # nothing was written, the file is left as it was
    assert file.read_text(encoding="utf-8") == content


@freeze_time("2026-09-30")
def test_open_or_create_task_reaches_a_folder_renamed_by_hand(tmp_path):
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()
    (folder / "EmbalagemAlteracaoFormulario.md").write_text(
        "# 18/09/2026\n\nnotas\n", encoding="utf-8"
    )

    # pasting the folder name is what a user reaching for the task does
    result = open_or_create_task(tmp_path, "EmbalagemAlteracaoFormulario")

    assert [path.name for path in tmp_path.iterdir()] == [folder.name]
    assert result.file == folder / "EmbalagemAlteracaoFormulario.md"


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


def test_move_task_moves_the_folder_with_what_it_carries(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "note.txt").write_text("a note", encoding="utf-8")
    content = file.read_text(encoding="utf-8")
    category = tmp_path / "Veritas"
    category.mkdir()

    moved = move_task(file.parent, category)

    assert moved == category / "260918 - Foo"
    assert moved.is_dir()
    assert (moved / "Foo.md").read_text(encoding="utf-8") == content
    assert (moved / "note.txt").read_text(encoding="utf-8") == "a note"
    assert not (tmp_path / "260918 - Foo").exists()


def test_move_task_in_the_category_it_already_stands_in_does_nothing(
    tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")

    moved = move_task(file.parent, tmp_path)

    assert moved == file.parent
    assert file.is_file()


def test_move_task_refuses_a_name_the_category_already_holds(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    category.mkdir()
    taken = category / "260918 - Foo"
    taken.mkdir()

    with pytest.raises(TaskError):
        move_task(file.parent, category)

    # nothing moved: the task stands where it was and the one of the category
    # is left alone
    assert file.is_file()
    assert list(taken.iterdir()) == []


def test_move_task_refuses_a_category_inside_the_task(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    inside = file.parent / "inside"
    inside.mkdir()

    with pytest.raises(TaskError):
        move_task(file.parent, inside)

    assert file.is_file()
    assert inside.is_dir()


def test_move_task_wraps_a_failure_of_the_filesystem(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    category.mkdir()

    def fail(self, target):
        raise OSError("the disk said no")

    monkeypatch.setattr(Path, "rename", fail)

    with pytest.raises(TaskError, match="the disk said no"):
        move_task(file.parent, category)

    assert file.is_file()


@freeze_time("2026-09-30")
def test_rename_task_keeps_the_date(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "F Society Everbind")

    assert result.file == tmp_path / "260918 - FSocietyEverbind" / "FSocietyEverbind.md"
    assert result.message == "Renamed: 260918 - FSocietyEverbind"


def test_rename_task_moves_the_reminders_of_the_task(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")
    path = reminders.reminders_path()
    reminders.add(path, datetime.datetime(2026, 10, 1, 9, 0), "", "260918 - FSociety", "F Society")  # noqa: DTZ001

    rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    [reminder] = reminders.load(path)
    assert (reminder.task, reminder.title) == ("260918 - Everbind", "Everbind")


def test_rename_task_reports_reminders_it_could_not_update(tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "FSociety")

    def failing(*args):
        raise OSError("read-only")

    monkeypatch.setattr(reminders, "follow_rename", failing)

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.message == "Renamed: 260918 - Everbind (reminders not updated)"
    assert (tmp_path / "260918 - Everbind" / "Everbind.md").is_file()


def test_rename_task_does_not_touch_the_content(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    # a heading naming the old title, free text, a second level heading and a
    # date in another of the accepted forms: none of it belongs to the name
    content = "# FSociety\n\n18/09/2026\n\n## Notes\n\n# FSociety\n\nbody\n"
    file.write_text(content, encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == content


def test_rename_task_leaves_a_file_without_any_content(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    file.write_text("", encoding="utf-8")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert result.file.read_text(encoding="utf-8") == ""


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

    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert (tmp_path / "260917 - FSocietyEverbind").is_dir()


def test_rename_task_rejects_a_title_an_archive_holds(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    archive = tmp_path / "260930 - Everbind.zip"
    archive.write_bytes(b"zip")

    with pytest.raises(TaskError, match="already archived"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert (tmp_path / "260918 - FSociety").is_dir()
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert archive.is_file()


def test_rename_task_rejects_a_task_that_is_archived(tmp_path, make_task):
    file = make_task(tmp_path, "260918", "FSociety")
    archive = tmp_path / "260918 - FSociety.zip"
    archive.write_bytes(b"zip")

    with pytest.raises(TaskError, match="already archived"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")

    assert (tmp_path / "260918 - FSociety").is_dir()
    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert archive.is_file()


def test_rename_task_rejects_a_title_of_another_date(tmp_path, make_task):
    # a title is unique in a directory, whichever date the task it clashes with
    # carries, so renaming must not be the way to end up with two of one title
    other = make_task(tmp_path, "260930", "FSociety")
    file = make_task(tmp_path, "260918", "Veritas")

    with pytest.raises(TaskError, match="already a task here"):
        rename_task(tmp_path / "260918 - Veritas", "Veritas", "F Society")

    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"
    assert other.read_text(encoding="utf-8") == "# 30/09/2026\n\n"
    assert not (tmp_path / "260918 - FSociety").exists()


@pytest.mark.parametrize("raw_title", ["FSOCIETY", "FSociety", "fsociety", "fSociety"])
def test_rename_task_rejects_a_clash_in_any_case(tmp_path, make_task, raw_title):
    # standardize_string puts the first letter up and the rest down, so every
    # spelling of the title lands on the same one before the clash test sees it
    make_task(tmp_path, "260917", "FSociety")
    file = make_task(tmp_path, "260918", "Able")

    with pytest.raises(TaskError, match="already a task here"):
        rename_task(tmp_path / "260918 - Able", "Able", raw_title)

    assert file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"


@freeze_time("2026-09-30")
def test_rename_task_only_changes_the_case(tmp_path, make_task):
    make_task(tmp_path, "260918", "AbCd")

    result = rename_task(tmp_path / "260918 - AbCd", "AbCd", "abcd")

    # the lookup ignores the case, so without leaving the folder out of it this
    # would be a task clashing with itself
    assert [path.name for path in tmp_path.iterdir()] == ["260918 - Abcd"]
    assert result.file == tmp_path / "260918 - Abcd" / "Abcd.md"
    assert result.file.read_text(encoding="utf-8") == "# 18/09/2026\n\n"


def test_rename_task_rejects_a_folder_without_markdown(tmp_path):
    (tmp_path / "260918 - FSociety").mkdir()

    with pytest.raises(TaskError, match="no Markdown file"):
        rename_task(tmp_path / "260918 - FSociety", "FSociety", "Everbind")


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
