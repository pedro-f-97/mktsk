import pytest
from freezegun import freeze_time

from mktsk.helpers import TaskError
from mktsk.tasks import (
    open_or_create_task,
    resume_task,
)


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


@freeze_time("2026-09-30")
def test_resume_task_uses_the_given_folder(tmp_path, make_task):
    make_task(tmp_path, "260918", "FSociety")
    folder = tmp_path / "260918 - FSociety"

    result = resume_task(folder, "FSociety")

    assert result.file == folder / "FSociety.md"
    assert "## 30/09/2026" in result.file.read_text(encoding="utf-8")


@freeze_time("2026-09-30")
def test_resume_task_keeps_the_caps_the_folder_carries(tmp_path):
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()
    original = folder / "EmbalagemAlteracaoFormulario.md"
    original.write_text(
        "# EmbalagemAlteracaoFormulario\n\n## 18/09/2026\n\nnotas\n", encoding="utf-8"
    )

    result = resume_task(folder, "Embalagemalteracaoformulario")

    # the .md is the one that was there, and nothing was signed on top of it
    assert [path.name for path in folder.iterdir()] == [original.name]
    assert result.file == original
    assert result.file.read_text(encoding="utf-8") == (
        "# EmbalagemAlteracaoFormulario\n\n## 18/09/2026\n\nnotas\n\n## 30/09/2026\n\n"
    )


@freeze_time("2026-09-30")
def test_open_or_create_task_reaches_a_folder_renamed_by_hand(tmp_path):
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()
    (folder / "EmbalagemAlteracaoFormulario.md").write_text(
        "# EmbalagemAlteracaoFormulario\n\nnotas\n", encoding="utf-8"
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
