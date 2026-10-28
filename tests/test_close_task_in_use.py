import zipfile

import pytest

import mktsk.main as cli
from mktsk import tasks
from mktsk.helpers import TaskError
from mktsk.tasks import TaskInUseError, close_task
from tests.gui_helpers import action_bar


def test_probe_failing_leaves_the_task_untouched(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    archive_path = tmp_path / "260918 - Foo.zip"
    original = file.read_text(encoding="utf-8")

    def fail_rename(*args, **kwargs):
        raise PermissionError("the file is in use")

    monkeypatch.setattr("mktsk.tasks.os.rename", fail_rename)

    with pytest.raises(TaskInUseError, match="in use"):
        close_task(folder, "Foo")

    # nothing is created and nothing is touched
    assert not archive_path.exists()
    assert folder.is_dir()
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == original


def test_folder_removal_failure_keeps_both(tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "260918", "Foo")
    folder = tmp_path / "260918 - Foo"
    archive_path = tmp_path / "260918 - Foo.zip"
    original = file.read_text(encoding="utf-8")

    def boom(path, *args, **kwargs):
        raise OSError("file in use")

    monkeypatch.setattr("mktsk.tasks.shutil.rmtree", boom)

    with pytest.raises(TaskError, match=r"archived .* but the folder could not"):
        close_task(folder, "Foo")

    # both are kept and the zip is intact
    assert archive_path.is_file()
    assert folder.is_dir()
    assert file.read_text(encoding="utf-8") == original
    with zipfile.ZipFile(archive_path) as archive:
        assert b'"closed"' in archive.read("260918 - Foo/Foo.md")


def test_close_with_a_file_in_use_shows_a_warning_and_keeps_the_task(
    window, tmp_path, make_task, monkeypatch, fake_messages
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    def raise_in_use(folder, title):
        raise tasks.TaskInUseError("some of its files are in use")

    monkeypatch.setattr("mktsk.tasks.close_task", raise_in_use)
    action_bar(window, file).close_button.click()

    assert fake_messages["warning"] == [
        (
            "Could not close the task: some of its files are in use. "
            "Close them and try again."
        )
    ]
    assert fake_messages["critical"] == []
    # the task stays open and unchanged
    assert file.parent.is_dir()
    assert not (tmp_path / "260918 - Foo.zip").exists()


def test_cli_close_with_a_task_in_use_exits_one_and_reports_it_on_stderr(
    monkeypatch, tmp_path, make_task, capsys
):
    make_task(tmp_path, "260918", "Foo")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv", ["mktsk", "--folder", str(tmp_path), "--close", "Foo"]
    )

    def raise_in_use(folder, title):
        raise tasks.TaskInUseError(
            f"Could not close the task '{title}': some of its files are in use. "
            "Close them and try again."
        )

    monkeypatch.setattr("mktsk.tasks.close_task", raise_in_use)

    result = cli.main()

    assert result == 1
    captured = capsys.readouterr()
    assert "Foo" in captured.err
    assert "in use" in captured.err
    assert captured.out == ""
