from pathlib import Path

import pytest
from freezegun import freeze_time
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QMessageBox

from mktsk.gui import MainWindow
from mktsk.gui import main as gui_main


@pytest.fixture
def window(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings=settings)
    win.show()
    qtbot.addWidget(win)
    return win

@pytest.fixture
def fake_open(monkeypatch):
    opened = []

    def fake_open_file(path):
        opened.append(path)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)
    return opened

@pytest.fixture
def fake_messages(monkeypatch):
    messages = {"critical": [], "warning": []}
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args: messages["critical"].append(args[2])
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: messages["warning"].append(args[2])
    )
    return messages


def test_initial_directory_defaults_to_cwd(window):
    assert window.current_directory == Path.cwd().resolve()

def test_navigate_to_lists_contents(window, tmp_path):
    (tmp_path / "play").mkdir()
    (tmp_path / "a.md").touch()

    window.navigate_to(tmp_path)

    labels = [window.file_list.item(i).text() for i in range(window.file_list.count())]
    assert labels == ["play/", "a.md"]

def test_navigate_to_invalid_directory_falls_back(window, tmp_path):
    window.navigate_to(tmp_path / "missing")

    assert window.current_directory == Path.cwd().resolve()

def test_go_up(window, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    window.navigate_to(sub)

    window.go_up()

    assert window.current_directory == tmp_path.resolve()

def test_go_up_at_root_stays(window):
    root = Path(Path.cwd().anchor)
    window.navigate_to(root)

    window.go_up()

    assert window.current_directory == root

def test_double_click_enters_directory(qtbot, window, tmp_path):
    sub = tmp_path / "play"
    sub.mkdir()
    window.navigate_to(tmp_path)

    window.file_list.itemDoubleClicked.emit(window.file_list.item(0))

    assert window.current_directory == sub.resolve()

def test_double_click_opens_md(qtbot, window, tmp_path, fake_open):
    (tmp_path / "a.md").touch()
    window.navigate_to(tmp_path)
    assert [window.file_list.item(i).text() for i in range(window.file_list.count())] == ["a.md"]

    window.file_list.itemDoubleClicked.emit(window.file_list.item(0))

    assert fake_open == [tmp_path / "a.md"]

def test_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    window.open_with_default_app(tmp_path / "a.md")

    assert len(fake_messages["warning"]) == 1
    assert "Could not open file" in fake_messages["warning"][0]

@freeze_time("2026-09-28")
def test_create_task(qtbot, window, tmp_path, fake_open):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Test Task")
    qtbot.keyClick(window.title_input, Qt.Key.Key_Return)

    folder = tmp_path / "260928 - TestTask"
    file = folder / "TestTask.md"
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == "# TestTask\n\n## 28/09/2026\n\n"
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert "260928 - TestTask/" in [window.file_list.item(i).text() for i in range(window.file_list.count())]

def test_create_task_empty_title(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.create_task()

    assert fake_messages["critical"] == ["Invalid task description."]
    assert list(tmp_path.iterdir()) == []

def test_create_task_empty_standardized(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("!!!")

    window.create_task()

    assert fake_messages["critical"] == ["invalid task description"]
    assert list(tmp_path.iterdir()) == []

def test_create_task_reserved_name(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("con")

    window.create_task()

    assert fake_messages["critical"] == ["'Con' is a reserved name"]
    assert list(tmp_path.iterdir()) == []

@freeze_time("2026-09-28")
def test_create_task_collision_opens_existing(window, tmp_path, fake_open):
    existing_folder = tmp_path / "260928 - TestTask"
    existing_folder.mkdir()
    existing_file = existing_folder / "TestTask.md"
    existing_file.write_text("# existing notes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert existing_file.read_text(encoding="utf-8") == "# existing notes\n"
    assert fake_open == [existing_file]

@freeze_time("2026-09-28")
def test_create_task_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert fake_messages["critical"] == []
    assert len(fake_messages["warning"]) == 1
    assert (tmp_path / "260928 - TestTask" / "TestTask.md").is_file()
    assert window.title_input.text() == ""

def test_choose_directory(window, tmp_path, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(tmp_path),
    )
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()

def test_choose_directory_cancelled(window, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: "",
    )
    before = window.current_directory
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == before

def test_up_button_navigates_up(window, tmp_path, qtbot):
    sub = tmp_path / "sub"
    sub.mkdir()
    window.navigate_to(sub)

    qtbot.mouseClick(window.up_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()

def test_refresh_button_reloads(window, tmp_path, qtbot):
    window.navigate_to(tmp_path)
    (tmp_path / "new.md").touch()

    qtbot.mouseClick(window.refresh_button, Qt.MouseButton.LeftButton)

    labels = [window.file_list.item(i).text() for i in range(window.file_list.count())]
    assert labels == ["new.md"]

def test_refresh_missing_directory(window, tmp_path):
    window.current_directory = tmp_path / "a.md"

    window.refresh()

    assert window.file_list.count() == 0

def test_close_saves_last_path(window, tmp_path):
    window.navigate_to(tmp_path)
    window.close()

    assert window.settings.value("last_path") == str(tmp_path.resolve())

def test_module_entry_point_uses_gui_main():
    from mktsk import __main__ as module

    assert module.main is gui_main