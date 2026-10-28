"""The single reminders dropdown button of the action bar."""

from typing import ClassVar

from PySide6.QtWidgets import QDialog

from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab, task_listing


class _FakeTray:
    """Records nothing: the tests never reach a notification."""

    def notify(self, title, message):
        pass


def _scheduler(tmp_path):
    return ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")


class _AcceptDialog:
    """Stands in for the add dialog and accepts at once."""

    def __init__(self, task_title, parent=None):
        self.task_title = task_title

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Accepted

    def due(self):
        import datetime

        return datetime.datetime(2026, 10, 27, 12, 0)  # noqa: DTZ001

    def message(self):
        return "note"


class _RejectDialog(_AcceptDialog):
    """Stands in for the add dialog and cancels at once."""

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Rejected


def test_one_reminders_button_with_a_menu(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    reminders = bar.reminder_buttons()
    assert len(reminders) == 1
    assert reminders[0] is bar.reminders_button
    assert bar.reminders_button.toolTip() == "Reminders"
    assert bar.reminders_button.text() == ""
    actions = bar.reminders_menu.actions()
    assert [action.text() for action in actions] == ["Add reminder...", "Reminders..."]


def test_the_bell_sits_after_state_and_before_archive(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    x = lambda button: button.geometry().x()
    assert x(bar.state_button) < x(bar.reminders_button)
    assert x(bar.reminders_button) < x(bar.close_button)
    x_positions = [x(b) for b in bar.buttons() + bar.reminder_buttons()]
    assert x(bar.close_button) == max(x_positions)


def test_no_bell_without_a_scheduler(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]


def test_no_bell_in_the_closed_tab(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    close_task(file.parent, "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "261027 - Teste.zip", "Closed")

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]


def test_adding_runs_the_same_flow_as_before(window, tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _AcceptDialog)

    action_bar(window, file).reminders_menu.actions()[0].trigger()

    [stored] = scheduler.reminders()
    assert stored.task == "261027 - MyTask"
    assert stored.title == "My Task"
    assert stored.message == "note"
    assert stored.due.hour == 12


def test_cancelling_adds_nothing(window, tmp_path, make_task, monkeypatch):
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _RejectDialog)

    action_bar(window, file).reminders_menu.actions()[0].trigger()

    assert scheduler.reminders() == []


def test_reminders_opens_the_popup_for_the_selected_task(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler
    seen = []

    class _Dialog:
        def __init__(self, *args):
            seen.append(args)

        def exec(self):
            from PySide6.QtWidgets import QDialog

            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("mktsk.gui.tasklist.RemindersDialog", _Dialog)

    action_bar(window, file).reminders_menu.actions()[1].trigger()

    assert seen[0][:3] == (scheduler, "261027 - MyTask", "My Task")


class _NeverOpenedDialog:
    """Stands in for a dialog and records that it was asked for."""

    calls: ClassVar[list] = []

    def __init__(self, *args):
        _NeverOpenedDialog.calls.append(args)

    def exec(self):
        from PySide6.QtWidgets import QDialog

        return QDialog.DialogCode.Rejected


def _clear_dialog_spy():
    _NeverOpenedDialog.calls = []


def test_no_reminder_without_a_scheduler(window, tmp_path, make_task, monkeypatch):
    """With no scheduler on the window, neither reminder action does anything.

    The menu actions are still connected to the handlers, so both run straight
    into the early return of `_reminder_target`: no dialog opens and nothing
    is stored.
    """
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)

    _clear_dialog_spy()
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _NeverOpenedDialog)
    monkeypatch.setattr("mktsk.gui.tasklist.RemindersDialog", _NeverOpenedDialog)

    bar = action_bar(window, file)

    bar.reminders_menu.actions()[0].trigger()
    bar.reminders_menu.actions()[1].trigger()

    assert _NeverOpenedDialog.calls == []


def test_no_reminder_without_a_selected_task(
    window, tmp_path, make_task, monkeypatch
):
    """With a scheduler but no task selected, neither reminder action does anything.

    Clearing the selection makes `_reminder_target` return None, so no reminder
    is stored and no dialog opens.
    """
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler

    _clear_dialog_spy()
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _NeverOpenedDialog)
    monkeypatch.setattr("mktsk.gui.tasklist.RemindersDialog", _NeverOpenedDialog)

    bar = action_bar(window, file)
    task_listing(window).setCurrentItem(None)

    bar.reminders_menu.actions()[0].trigger()
    bar.reminders_menu.actions()[1].trigger()

    assert scheduler.reminders() == []
    assert _NeverOpenedDialog.calls == []
