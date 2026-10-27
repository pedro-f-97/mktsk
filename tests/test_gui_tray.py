"""The system tray, close-to-tray and real Quit behaviour."""

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QSystemTrayIcon

from mktsk import gui
from mktsk.gui import MainWindow
from mktsk.gui.app_icon import app_icon
from mktsk.gui.tray import TrayController


def _make_window(qtbot, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    window.show()
    qtbot.addWidget(window)
    monkeypatch.setattr("mktsk.gui.tray.tray_available", lambda: True)
    tray = TrayController(window)
    window.tray_controller = tray
    return window, tray


def test_close_ignored_and_window_hidden_to_tray(qtbot, tmp_path, monkeypatch):
    window, _tray = _make_window(qtbot, tmp_path, monkeypatch)
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is False
    assert window.isHidden()
    assert window.settings.contains("window/geometry")


def test_tray_menu_has_open_and_quit(qtbot, tmp_path, monkeypatch):
    _window, tray = _make_window(qtbot, tmp_path, monkeypatch)
    actions = [action.text() for action in tray.tray.contextMenu().actions()]
    assert actions == ["Open", "Quit"]


def test_tray_icon_is_the_app_icon(qtbot, tmp_path, monkeypatch):
    icon = app_icon()
    monkeypatch.setattr("mktsk.gui.tray.app_icon", lambda: icon)
    monkeypatch.setattr("mktsk.gui.tray.tray_available", lambda: True)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    window.show()
    qtbot.addWidget(window)
    tray = TrayController(window)
    window.tray_controller = tray
    assert tray.tray.icon().cacheKey() == icon.cacheKey()


def test_open_shows_and_raises_the_window(qtbot, tmp_path, monkeypatch):
    window, tray = _make_window(qtbot, tmp_path, monkeypatch)
    window.hide()
    tray._show()
    assert window.isVisible()


def test_left_click_activation_shows_the_window(qtbot, tmp_path, monkeypatch):
    window, tray = _make_window(qtbot, tmp_path, monkeypatch)
    window.hide()
    tray.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
    assert window.isVisible()


def test_other_activation_reasons_do_not_show_the_window(
    qtbot, tmp_path, monkeypatch
):
    window, tray = _make_window(qtbot, tmp_path, monkeypatch)
    window.hide()
    tray.tray.activated.emit(QSystemTrayIcon.ActivationReason.MiddleClick)
    assert window.isHidden()


def test_quit_releases_the_instance_lock(qtbot, tmp_path, monkeypatch):
    window, _tray = _make_window(qtbot, tmp_path, monkeypatch)
    released = []

    class _FakeLock:
        def unlock(self):
            released.append(True)

    window._instance_lock = _FakeLock()
    monkeypatch.setattr("mktsk.gui.window.QApplication.quit", lambda: None)
    window.quit_application()
    assert released == [True]


def test_quit_saves_layout_sets_flag_and_next_close_is_accepted(
    qtbot, tmp_path, monkeypatch
):
    window, _tray = _make_window(qtbot, tmp_path, monkeypatch)
    monkeypatch.setattr("mktsk.gui.window.QApplication.quit", lambda: None)
    window.quit_application()
    assert window._quitting is True
    assert window.settings.contains("window/geometry")
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is True


def test_close_accepted_when_saving_session(qtbot, tmp_path, monkeypatch):
    window, _tray = _make_window(qtbot, tmp_path, monkeypatch)
    monkeypatch.setattr(
        QGuiApplication, "isSavingSession", staticmethod(lambda: True)
    )
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is True


def test_close_accepted_without_tray(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("mktsk.gui.tray.tray_available", lambda: False)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    window.show()
    qtbot.addWidget(window)
    window.tray_controller = None
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is True
    assert window.settings.contains("window/geometry")


def _startup(monkeypatch, tmp_path, tray_is_available):
    windows = []
    instances = []
    quit_on_last_closed = []

    class _FakeApplication:
        def __init__(self, arguments):
            self.arguments = arguments
            instances.append(self)

        def exec(self):
            return 7

        @staticmethod
        def setQuitOnLastWindowClosed(value):
            quit_on_last_closed.append(value)

    def window(**kwargs):
        created = _FakeWindow()
        windows.append(created)
        return created

    monkeypatch.setattr("mktsk.gui.QApplication", _FakeApplication)
    monkeypatch.setattr("mktsk.gui.MainWindow", window)
    monkeypatch.setattr("mktsk.gui.ensure_base_folder", lambda: tmp_path)
    monkeypatch.setattr("mktsk.gui.acquire_instance_lock", lambda directory: object())
    monkeypatch.setattr("mktsk.gui.tray_available", lambda: tray_is_available)
    return windows, instances, quit_on_last_closed


class _FakeWindow:
    def __init__(self):
        self.shown = False
        self.quit_application_called = False

    def show(self):
        self.shown = True

    def quit_application(self):
        self.quit_application_called = True

    def attach_reminder_scheduler(self, scheduler):
        self.reminder_scheduler = scheduler


def test_startup_sets_quit_on_last_window_closed_only_when_tray_available(
    monkeypatch, tmp_path
):
    for available, expected in ((True, [False]), (False, [])):
        windows, applications, quit_on_last_closed = _startup(
            monkeypatch, tmp_path, available
        )
        assert gui.main() == 7
        assert quit_on_last_closed == expected
        assert len(windows) == 1
        assert windows[0].shown is True
        windows.clear()
        applications.clear()
        quit_on_last_closed.clear()
