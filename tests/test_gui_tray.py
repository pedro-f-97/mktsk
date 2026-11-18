"""The system tray, close-to-tray and real Quit behaviour."""

import datetime
from typing import cast

from PySide6.QtCore import QLockFile, QSettings
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from mktsk import config, gui
from mktsk.gui import MainWindow, ReminderScheduler
from mktsk.gui.app_icon import app_icon
from mktsk.gui.single_instance import acquire_instance_lock
from mktsk.gui.tray import TrayController
from mktsk.reminders import add, load


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

    window._instance_lock = cast(QLockFile, _FakeLock())
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


# The reminder scheduler: poll, fire, stagger, and the startup check.


class _FakeTray:
    """Records notify calls instead of showing real notifications."""

    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.notifications.append((title, message))


def _due(y, m, d, h, mi):
    return datetime.datetime(y, m, d, h, mi)  # noqa: DTZ001


def test_check_fires_due_reminders_removes_them_and_emits_changed(qtbot, tmp_path):
    path = tmp_path / "reminders.json"
    tray = _FakeTray()
    scheduler = ReminderScheduler(tray, path)
    add(path, _due(2026, 10, 27, 9, 0), "hello", "261027 - Alpha", "Alpha")
    add(path, _due(2026, 10, 27, 9, 1), "", "261027 - Beta", "Beta")

    emitted = []
    scheduler.changed.connect(lambda: emitted.append(True))

    scheduler.check(now=_due(2026, 10, 27, 9, 1))
    qtbot.wait(2000)

    assert tray.notifications == [
        ("mktsk", "Alpha: hello"),
        ("mktsk", "Beta"),
    ]
    assert load(path) == []
    assert emitted == [True]


def test_check_nothing_due_fires_nothing_and_does_not_emit(qtbot, tmp_path):
    path = tmp_path / "reminders.json"
    tray = _FakeTray()
    scheduler = ReminderScheduler(tray, path)
    add(path, _due(2026, 10, 27, 10, 0), "future", "261027 - Alpha", "Alpha")

    emitted = []
    scheduler.changed.connect(lambda: emitted.append(True))

    scheduler.check(now=_due(2026, 10, 27, 9, 0))

    assert tray.notifications == []
    assert [r.message for r in load(path)] == ["future"]
    assert emitted == []


def test_check_staggers_multiple_due_notifications(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "reminders.json"
    shots = []
    monkeypatch.setattr(
        "mktsk.gui.reminders_scheduler.QTimer.singleShot",
        lambda delay, slot: shots.append(delay),
    )
    tray = _FakeTray()
    scheduler = ReminderScheduler(tray, path)
    add(path, _due(2026, 10, 27, 8, 0), "early", "261027 - Alpha", "Alpha")
    add(path, _due(2026, 10, 27, 8, 1), "mid", "261027 - Beta", "Beta")
    add(path, _due(2026, 10, 27, 8, 2), "late", "261027 - Gamma", "Gamma")

    scheduler.check(now=_due(2026, 10, 27, 8, 2))

    assert shots == [1500, 3000]
    # the first notification is immediate, the rest are only scheduled
    assert tray.notifications == [("mktsk", "Alpha: early")]


def test_add_and_remove_persist_and_emit_changed(qtbot, tmp_path):
    path = tmp_path / "reminders.json"
    tray = _FakeTray()
    scheduler = ReminderScheduler(tray, path)

    emitted = []
    scheduler.changed.connect(lambda: emitted.append(True))

    reminder = scheduler.add(_due(2026, 10, 27, 9, 0), "m", "261027 - Alpha", "Alpha")
    assert emitted == [True]
    assert load(path) == [reminder]
    assert scheduler.reminders() == [reminder]
    assert scheduler.for_task("261027 - Alpha") == [reminder]
    assert scheduler.for_task("261027 - Beta") == []

    assert scheduler.remove(reminder.id) is True
    assert emitted == [True, True]
    assert load(path) == []

    assert scheduler.remove("unknown-id") is False
    assert emitted == [True, True]


def test_start_activates_30_second_timer_and_stop_deactivates_it(qtbot, tmp_path):
    scheduler = ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")
    assert scheduler._timer.interval() == 30_000
    assert not scheduler._timer.isActive()

    scheduler.start()
    assert scheduler._timer.isActive()

    scheduler.stop()
    assert not scheduler._timer.isActive()


def test_tray_notify_calls_show_message(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("mktsk.gui.tray.tray_available", lambda: True)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = gui.MainWindow(settings=settings)
    window.show()
    qtbot.addWidget(window)
    tray = TrayController(window)
    window.tray_controller = tray

    shown = []
    monkeypatch.setattr(
        tray.tray,
        "showMessage",
        lambda title, message, icon, msecs: shown.append((title, message, icon, msecs)),
    )
    tray.notify("mktsk", "Alpha: hello")
    tray.notify("mktsk", "Beta")

    assert shown == [
        ("mktsk", "Alpha: hello", QSystemTrayIcon.MessageIcon.Information, 10_000),
        ("mktsk", "Beta", QSystemTrayIcon.MessageIcon.Information, 10_000),
    ]


def _scheduler_startup(monkeypatch, tmp_path, tray_is_available):
    windows = []
    trays = []
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
        created = _SchedulerWindow()
        windows.append(created)
        return created

    def tray_controller(window):
        created = _FakeTrayController()
        trays.append(created)
        return created

    monkeypatch.setattr("mktsk.gui.QApplication", _FakeApplication)
    monkeypatch.setattr("mktsk.gui.MainWindow", window)
    monkeypatch.setattr("mktsk.gui.ensure_base_folder", lambda: tmp_path)
    monkeypatch.setattr("mktsk.gui.acquire_instance_lock", lambda directory: object())
    monkeypatch.setattr("mktsk.gui.tray_available", lambda: tray_is_available)
    monkeypatch.setattr("mktsk.gui.TrayController", tray_controller)
    return windows, trays, instances, quit_on_last_closed


class _SchedulerWindow:
    def __init__(self):
        self.shown = False

    def show(self):
        self.shown = True

    def attach_reminder_scheduler(self, scheduler):
        self.reminder_scheduler = scheduler


class _FakeTrayController:
    pass


def test_startup_with_tray_creates_scheduler_checks_before_start(monkeypatch, tmp_path):
    created = []
    order = []

    class _FakeScheduler:
        def __init__(self, tray, path, parent=None):
            created.append((tray, path))

        def check(self, now=None):
            order.append("check")

        def start(self):
            order.append("start")

    monkeypatch.setattr("mktsk.gui.ReminderScheduler", _FakeScheduler)
    monkeypatch.setattr(
        "mktsk.gui.reminders_path", lambda: tmp_path / "reminders.json"
    )

    windows, trays, _, _ = _scheduler_startup(monkeypatch, tmp_path, True)
    assert gui.main() == 7
    assert len(windows) == 1 and windows[0].shown is True
    assert len(trays) == 1
    assert len(created) == 1
    assert created[0][1] == tmp_path / "reminders.json"
    assert order == ["check", "start"]


def test_startup_without_tray_creates_no_scheduler_and_touches_nothing(
    monkeypatch, tmp_path
):
    created = []

    class _FakeScheduler:
        def __init__(self, tray, path, parent=None):
            created.append((tray, path))

    monkeypatch.setattr("mktsk.gui.ReminderScheduler", _FakeScheduler)
    monkeypatch.setattr(
        "mktsk.gui.reminders_path", lambda: tmp_path / "reminders.json"
    )

    windows, trays, _, _ = _scheduler_startup(monkeypatch, tmp_path, False)
    assert gui.main() == 7
    assert len(windows) == 1 and windows[0].shown is True
    assert len(trays) == 0
    assert created == []
    assert not (tmp_path / "reminders.json").exists()


# The single-instance lock for the GUI.


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


class _InstanceWindow:
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
        created = _InstanceWindow()
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
