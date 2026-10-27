"""The reminder scheduler: poll, fire, stagger, and the startup check."""

import datetime

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QSystemTrayIcon

from mktsk import gui
from mktsk.gui import ReminderScheduler
from mktsk.gui.tray import TrayController
from mktsk.reminders import add, load


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


def _startup(monkeypatch, tmp_path, tray_is_available):
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
        created = _FakeWindow()
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


class _FakeWindow:
    def __init__(self):
        self.shown = False

    def show(self):
        self.shown = True


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

    windows, trays, _, _ = _startup(monkeypatch, tmp_path, True)
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

    windows, trays, _, _ = _startup(monkeypatch, tmp_path, False)
    assert gui.main() == 7
    assert len(windows) == 1 and windows[0].shown is True
    assert len(trays) == 0
    assert created == []
    assert not (tmp_path / "reminders.json").exists()
