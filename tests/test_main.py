import pytest
from freezegun import freeze_time

from mktsk.main import main, parse_arguments


def test_main(monkeypatch, tmp_path):
    folder = tmp_path / "my_folder"
    folder.mkdir()
    monkeypatch.chdir(folder)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main"],)

    opened_files = []

    def fake_open_file(file):
        opened_files.append(file)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)

    with freeze_time("2026-09-22"):
        result = main()

    final_folder = folder / "260922 - TestMain"
    final_file = final_folder / "TestMain.md"

    assert result == 0
    assert final_file.is_file()
    assert final_file.read_text(encoding="utf-8") == "# TestMain\n\n## 22/09/2026\n\n"
    assert opened_files == [final_file]

def test_main_empty_title(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "   "])

    result = main()

    assert result == 1
    assert list(tmp_path.iterdir()) == []

def test_main_invalid_title(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "!!!"])

    result = main()

    assert result == 1
    assert list(tmp_path.iterdir()) == []

def test_main_reserved_name(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "con"])

    result = main()

    assert result == 1
    assert "reserved" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []

def test_main_resumes_existing_task(monkeypatch, tmp_path):
    folder = tmp_path / "my_folder"
    folder.mkdir()
    monkeypatch.chdir(folder)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main"])

    existing_folder = folder / "260922 - TestMain"
    existing_folder.mkdir()
    existing_file = existing_folder / "TestMain.md"
    existing_file.write_text("# existing notes\n", encoding="utf-8")

    opened_files = []

    def fake_open_file(file):
        opened_files.append(file)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)

    with freeze_time("2026-09-22"):
        result = main()

    assert result == 0
    assert existing_file.read_text(encoding="utf-8") == (
        "# existing notes\n\n## 22/09/2026\n\n"
    )
    assert opened_files == [existing_file]

def test_main_finds_existing_task_by_title(monkeypatch, tmp_path, capsys):
    folder = tmp_path / "260918 - TestMain"
    folder.mkdir()
    file = folder / "TestMain.md"
    file.write_text("# TestMain\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main"])

    opened_files = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened_files.append)

    with freeze_time("2026-09-30"):
        result = main()

    assert result == 0
    assert opened_files == [file]
    assert file.read_text(encoding="utf-8") == (
        "# TestMain\n\n## 18/09/2026\n\nnotes\n\n## 30/09/2026\n\n"
    )
    assert "Opened: 260918 - TestMain" in capsys.readouterr().out
    assert not (tmp_path / "260930 - TestMain").exists()

def test_main_creates_when_task_is_in_a_subdirectory(monkeypatch, tmp_path):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260918 - TestMain"
    folder.mkdir()
    existing = folder / "TestMain.md"
    existing.write_text("# TestMain\n\n## 18/09/2026\n\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main"])

    opened_files = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened_files.append)

    with freeze_time("2026-09-30"):
        result = main()

    created = tmp_path / "260930 - TestMain" / "TestMain.md"

    assert result == 0
    assert opened_files == [created]
    assert existing.read_text(encoding="utf-8") == "# TestMain\n\n## 18/09/2026\n\n"

def test_main_open_failure_warns(monkeypatch, tmp_path, capsys):
    folder = tmp_path / "my_folder"
    folder.mkdir()
    monkeypatch.chdir(folder)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main"])

    def raise_error(file):
        raise OSError("test open error")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    with freeze_time("2026-09-22"):
        result = main()

    final_file = folder / "260922 - TestMain" / "TestMain.md"

    assert result == 0
    assert final_file.is_file()
    assert "Warning" in capsys.readouterr().out

def test_main_error(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "Test", "Main", "Error"],)

    def raise_error(*args):
        raise OSError("test error")

    monkeypatch.setattr("mktsk.workers.create_folder", raise_error)

    result = main()

    assert result == 1
    assert "Error: test error" in capsys.readouterr().out

def test_parse_arguments(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["mktsk", "Back", "to", "the", "Future"],
    )

    args = parse_arguments()

    assert args.title == ["Back", "to", "the", "Future"]
    assert args.rename is False

def test_parse_arguments_without_title(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2

def test_parse_arguments_for_rename(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "260918 - Foo", "Bar"])

    args = parse_arguments()

    assert args.rename is True
    assert args.title == ["260918 - Foo", "Bar"]

def test_parse_arguments_for_rename_without_a_new_title(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "260918 - Foo"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2

def test_parse_arguments_for_rename_keeps_a_new_title_of_several_words(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["mktsk", "--rename", "260918 - Foo", "Back", "to", "the", "Future"]
    )

    args = parse_arguments()

    assert args.title == ["260918 - Foo", "Back", "to", "the", "Future"]

def test_parse_arguments_for_list(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    args = parse_arguments()

    assert args.list is True
    assert args.title == []

def test_parse_arguments_for_list_with_a_title(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "Foo"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2

def test_parse_arguments_for_list_and_rename(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mktsk", "--list", "--rename", "260918 - Foo", "Bar"])

    with pytest.raises(SystemExit) as failure:
        parse_arguments()

    assert failure.value.code == 2

def test_main_list(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260923", "ItsAlive")
    make_task(tmp_path / "Veritas", "260924", "FSocietyEverbind")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = main()

    assert result == 0
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  23/09/2026  Its Alive\n"
        "  18/09/2026  Foo\n"
        "Veritas/\n"
        "  24/09/2026  F Society Everbind\n"
    )
    assert opened == []

def test_main_list_reads_the_title_as_words(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260923", "Task2")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    main()

    assert "  23/09/2026  Task 2\n" in capsys.readouterr().out

def test_main_list_keeps_the_categories_apart(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Able", "260919", "Foo")
    make_task(tmp_path / "Veritas", "260920", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    main()

    # the same title is a different task in each directory, and each gets its own
    assert capsys.readouterr().out == (
        f"{tmp_path.name}/\n"
        "  18/09/2026  Foo\n"
        "Able/\n"
        "  19/09/2026  Foo\n"
        "Veritas/\n"
        "  20/09/2026  Foo\n"
    )

def test_main_list_of_a_directory_without_tasks(monkeypatch, tmp_path, capsys):
    (tmp_path / "Veritas").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    result = main()

    assert result == 0
    assert capsys.readouterr().out == ""

def test_main_list_skips_a_task_folder_without_md(monkeypatch, tmp_path, capsys, make_task):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "260919 - Bar").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])

    main()

    assert "Bar" not in capsys.readouterr().out

def test_main_rename(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - OldTitle"
    folder.mkdir()
    file = folder / "OldTitle.md"
    file.write_text("# OldTitle\n\n## 18/09/2026\n\nnotes\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "New Title"])

    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = main()

    renamed_folder = tmp_path / "260918 - NewTitle"
    renamed_file = renamed_folder / "NewTitle.md"

    assert result == 0
    assert renamed_file.is_file()
    assert not folder.exists()
    assert renamed_file.read_text(encoding="utf-8") == (
        "# NewTitle\n\n## 18/09/2026\n\nnotes\n"
    )
    assert capsys.readouterr().out == f"Renamed: {renamed_folder.name}\n"
    # renaming is not working on the task, so nothing is opened
    assert opened == []

def test_main_rename_joins_a_new_title_given_in_words(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - OldTitle"
    folder.mkdir()
    (folder / "OldTitle.md").write_text("# OldTitle\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["mktsk", "--rename", folder.name, "Back", "to", "the", "Future"]
    )

    result = main()

    assert result == 0
    assert (tmp_path / "260918 - BackToTheFuture" / "BackToTheFuture.md").is_file()

def test_main_rename_to_the_title_it_already_has(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - OldTitle"
    folder.mkdir()
    file = folder / "OldTitle.md"
    file.write_text("# OldTitle\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "Old Title"])

    result = main()

    assert result == 0
    assert file.is_file()
    assert capsys.readouterr().out == f"Renamed: {folder.name}\n"

def test_main_rename_refuses_a_name_that_is_not_a_task_folder(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Veritas").mkdir()
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "Veritas", "Foo"])

    result = main()

    assert result == 1
    assert "Error: 'Veritas' is not a task folder" in capsys.readouterr().out

def test_main_rename_refuses_an_invalid_date_prefix(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "261318 - Foo").mkdir()
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "261318 - Foo", "Bar"])

    result = main()

    assert result == 1
    assert "is not a task folder" in capsys.readouterr().out

def test_main_rename_refuses_a_folder_that_is_not_there(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "260918 - Missing", "Foo"])

    result = main()

    assert result == 1
    assert "Error: '260918 - Missing' is not there" in capsys.readouterr().out

def test_main_rename_refuses_a_collision(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n", encoding="utf-8")
    taken = tmp_path / "260901 - Bar"
    taken.mkdir()
    (taken / "Bar.md").write_text("# Bar\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "Bar"])

    result = main()

    assert result == 1
    assert "'Bar' is already a task here" in capsys.readouterr().out
    assert (folder / "Foo.md").is_file()

def test_main_rename_refuses_a_blank_new_title(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "!!!"])

    result = main()

    assert result == 1
    assert "invalid task description" in capsys.readouterr().out

def test_main_rename_refuses_a_reserved_new_title(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "con"])

    result = main()

    assert result == 1
    assert "'Con' is a reserved name" in capsys.readouterr().out

def test_main_rename_refuses_a_task_without_markdown(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "260918 - Foo").mkdir()
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", "260918 - Foo", "Bar"])

    result = main()

    assert result == 1
    assert "'Foo' has no Markdown file" in capsys.readouterr().out

def test_main_rename_reports_a_failure_to_rename(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()
    (folder / "Foo.md").write_text("# Foo\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["mktsk", "--rename", folder.name, "Bar"])

    def raise_error(*args):
        raise OSError("test error")

    monkeypatch.setattr("mktsk.workers.rename_task", raise_error)

    result = main()

    assert result == 1
    assert "Error: test error" in capsys.readouterr().out