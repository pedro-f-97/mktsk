"""The single-instance lock for the GUI."""

from PySide6.QtWidgets import QMessageBox

from mktsk import config, gui
from mktsk.gui.single_instance import acquire_instance_lock


def _patch_config_path(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")


def test_first_acquire_returns_a_lock(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    lock = acquire_instance_lock(tmp_path)
    assert lock is not None
    lock.unlock()


def test_second_acquire_returns_none_while_held(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    assert acquire_instance_lock(tmp_path) is None
    first.unlock()


def test_acquire_succeeds_after_release(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    first.unlock()
    second = acquire_instance_lock(tmp_path)
    assert second is not None
    second.unlock()


class _FakeApplication:
    def __init__(self, arguments):
        self.arguments = arguments
        self.executed = False

    def exec(self):
        self.executed = True
        return 7


class _FakeWindow:
    def __init__(self):
        self.shown = False

    def show(self):
        self.shown = True


def test_startup_with_lock_held_shows_message_and_returns_zero(
    monkeypatch, tmp_path
):
    _patch_config_path(monkeypatch, tmp_path)
    windows = []
    instances = []

    def application(arguments):
        app = _FakeApplication(arguments)
        instances.append(app)
        return app

    def window(**kwargs):
        created = _FakeWindow()
        windows.append(created)
        return created

    monkeypatch.setattr(gui, "QApplication", application)
    monkeypatch.setattr(gui, "MainWindow", window)
    monkeypatch.setattr(gui, "ensure_base_folder", lambda: tmp_path)
    monkeypatch.setattr(gui, "acquire_instance_lock", lambda directory: None)

    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: messages.append(args[2])
    )

    assert gui.main() == 0
    assert instances[0].executed is False
    assert windows == []
    assert messages == [
        "mktsk is already running. Look for its icon in the system tray."
    ]
