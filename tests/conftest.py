import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from mktsk.gui import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def make_task():
    """Creates a task folder with its .md file, as mktsk would."""

    def create(directory, date, title):
        folder = directory / f"{date} - {title}"
        folder.mkdir(parents=True)
        file = folder / f"{title}.md"
        file.write_text(f"# {title}\n", encoding="utf-8")
        return file

    return create


@pytest.fixture
def window(qtbot, tmp_path):
    """The main window, pointed at a directory of its own and already shown."""
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings=settings)
    win.show()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def fake_open(monkeypatch):
    """Records what would have been opened, instead of opening it."""
    opened = []

    def fake_open_file(path):
        opened.append(path)

    monkeypatch.setattr("mktsk.helpers.open_file", fake_open_file)
    return opened


@pytest.fixture
def fake_messages(monkeypatch):
    """Records the message boxes that would have been shown."""
    messages = {"critical": [], "warning": []}
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args: messages["critical"].append(args[2])
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: messages["warning"].append(args[2])
    )
    return messages
