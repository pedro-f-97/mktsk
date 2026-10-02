from pathlib import Path

from mktsk.listing import find_task_folder


def test_find_task_folder_ignores_date(tmp_path):
    folder = tmp_path / "260918 - Foo"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Foo") == folder


def test_find_task_folder_ignores_the_case_of_the_title(tmp_path):
    # standardize_string lowers the capitals inside a title, so a folder renamed
    # by hand keeps ones the lookup would never produce. Copying its name into the
    # terminal has to reach the task, not create a second one
    folder = tmp_path / "260918 - EmbalagemAlteracaoFormulario"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Embalagemalteracaoformulario") == folder


def test_find_task_folder_excludes_a_folder(tmp_path):
    # how rename_task keeps a task from clashing with itself over the case alone
    folder = tmp_path / "260918 - AbCd"
    folder.mkdir()

    assert find_task_folder(tmp_path, "Abcd") == folder
    assert find_task_folder(tmp_path, "Abcd", exclude=folder) is None


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
