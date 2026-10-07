from pathlib import Path

import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.tasks import rename_task


@freeze_time("2026-09-30")
def test_rename_task_keeps_the_date(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")

    result = rename_task(tmp_path / "260918 - FSociety", "FSociety", "F Society Everbind")

    assert result.file == tmp_path / "260918 - FSocietyEverbind" / "FSocietyEverbind.md"
    assert result.message == "Renamed: 260918 - FSocietyEverbind"


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
