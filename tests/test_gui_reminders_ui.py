"""The reminders UI: icons, row buttons, the add dialog, the list and the popup."""

import datetime

from PySide6.QtCore import QDate, QDateTime, QPoint, QSize, Qt, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog

from mktsk.gui.icons import _draw_bell, _draw_bell_plus, _stroked_icon
from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.gui.reminders_ui import (
    AddReminderDialog,
    RemindersDialog,
    RemindersList,
)
from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab


class _FakeTray:
    """Records nothing: the tests never reach a notification."""

    def notify(self, title, message):
        pass


class _Clock:
    """Stands in for the datetime class, so the dialogs open at a set time."""

    now = staticmethod(lambda: _at(10, 30))


def _scheduler(tmp_path):
    return ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")


def _at(hour, minute=0, second=0):
    return datetime.datetime(2026, 10, 27, hour, minute, second)  # noqa: DTZ001


def _due(hour, minute=0, day=27):
    return datetime.datetime(2026, 10, day, hour, minute)  # noqa: DTZ001


def _moment(hour, minute=0, second=0):
    return QDateTime(
        QDate(2026, 10, 27),
        QTime(hour, minute, second),
    )


def _shown_list(qtbot, scheduler, task=None):
    widget = RemindersList(scheduler, task)
    qtbot.addWidget(widget)
    widget.resize(480, 240)
    widget.show()
    return widget


def _click_cell(qtbot, widget, row, column):
    item = widget.topLevelItem(row)
    rect = widget.visualItemRect(item)
    x = widget.columnViewportPosition(column) + widget.columnWidth(column) // 2
    qtbot.mouseClick(
        widget.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(x, rect.center().y())
    )


class _AcceptDialog:
    """Stands in for the add dialog and accepts at once."""

    def __init__(self, task_title, parent=None):
        self.task_title = task_title

    def exec(self):
        return QDialog.DialogCode.Accepted

    def due(self):
        return _due(12)

    def message(self):
        return "note"


class _RejectDialog(_AcceptDialog):
    """Stands in for the add dialog and cancels at once."""

    def exec(self):
        return QDialog.DialogCode.Rejected


def test_both_bell_icons_draw_at_several_sizes(qapp):
    for draw in (_draw_bell, _draw_bell_plus):
        icon = _stroked_icon(QColor("#000000"), draw)
        assert icon.isNull() is False
        for size in (12, 16, 18, 24):
            assert icon.pixmap(QSize(size, size)).isNull() is False


def test_the_row_bar_offers_the_reminder_buttons_for_an_open_task(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    assert [button.toolTip() for button in bar.reminder_buttons()] == [
        "Add reminder",
        "Reminders",
    ]
    for button in bar.reminder_buttons():
        assert button.text() == ""
        assert button.isVisible() is True
        assert button.iconSize() == bar.open_button.iconSize()
        assert button.autoRaise() is True


def test_the_row_bar_offers_no_reminders_without_a_scheduler(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False, False]


def test_the_closed_tab_offers_no_reminder_buttons(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    close_task(file.parent, "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "261027 - Teste.zip", "Closed")

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False, False]


def test_the_add_dialog_opens_at_the_next_whole_hour(qapp, monkeypatch):
    monkeypatch.setattr("mktsk.gui.reminders_ui.datetime", _Clock)

    dialog = AddReminderDialog("Teste")

    assert dialog.due() == _at(11)


def test_ok_stands_only_while_the_chosen_minute_is_in_the_future(qapp, monkeypatch):
    monkeypatch.setattr("mktsk.gui.reminders_ui.datetime", _Clock)
    dialog = AddReminderDialog("Teste")
    assert dialog.ok_button.isEnabled() is True

    dialog.date_edit.setDateTime(_moment(10, 30))
    assert dialog.ok_button.isEnabled() is False

    dialog.date_edit.setDateTime(_moment(9, 0))
    assert dialog.ok_button.isEnabled() is False

    dialog.date_edit.setDateTime(_moment(10, 31))
    assert dialog.ok_button.isEnabled() is True


def test_the_add_dialog_reads_a_stripped_message_and_a_minute_due(qapp):
    dialog = AddReminderDialog("Teste")
    dialog.date_edit.setDateTime(_moment(11, 5, 42))
    dialog.message_input.setText("  call back  ")

    assert dialog.due() == _at(11, 5)
    assert dialog.due().tzinfo is None
    assert dialog.message() == "call back"


def test_accepting_the_add_dialog_stores_the_reminder(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _AcceptDialog)

    action_bar(window, file).add_reminder_button.click()

    [stored] = scheduler.reminders()
    assert stored.task == "261027 - MyTask"
    assert stored.title == "My Task"
    assert stored.message == "note"
    assert stored.due == _due(12)


def test_cancelling_the_add_dialog_adds_nothing(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "261027", "MyTask")
    window.navigate_to(tmp_path)
    scheduler = _scheduler(tmp_path)
    window.reminder_scheduler = scheduler
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _RejectDialog)

    action_bar(window, file).add_reminder_button.click()

    assert scheduler.reminders() == []


def test_the_reminders_button_opens_the_popup_for_the_selected_task(
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
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("mktsk.gui.tasklist.RemindersDialog", _Dialog)

    action_bar(window, file).reminders_button.click()

    assert seen[0][:3] == (scheduler, "261027 - MyTask", "My Task")


def test_the_filtered_list_shows_one_task_sorted_by_due(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(12), "second", "261027 - Alpha", "Alpha")
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    scheduler.add(_due(10), "other", "261027 - Beta", "Beta")

    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")

    assert widget.columnCount() == 3
    assert [
        widget.headerItem().text(column) for column in range(widget.columnCount())
    ] == ["When", "Message", ""]
    assert [widget.topLevelItem(row).text(1) for row in range(2)] == [
        "first",
        "second",
    ]
    assert widget.topLevelItem(0).text(0) == "27/10/2026 09:00"


def test_the_unfiltered_list_carries_a_task_column(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(12), "second", "261027 - Alpha", "Alpha")
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    scheduler.add(_due(10), "other", "261027 - Beta", "Beta")

    widget = _shown_list(qtbot, scheduler)

    assert widget.columnCount() == 4
    assert [
        widget.headerItem().text(column) for column in range(widget.columnCount())
    ] == ["When", "Message", "Task", ""]
    assert [widget.topLevelItem(row).text(2) for row in range(3)] == [
        "Alpha",
        "Beta",
        "Alpha",
    ]


def test_a_reminder_without_a_message_shows_its_title(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "", "261027 - Alpha", "Alpha")

    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")

    assert widget.topLevelItem(0).text(1) == "Alpha"


def test_the_delete_cell_removes_the_reminder_at_once(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    scheduler.add(_due(10), "second", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")

    _click_cell(qtbot, widget, 0, 2)

    assert [reminder.message for reminder in scheduler.for_task("261027 - Alpha")] == [
        "second"
    ]
    assert widget.topLevelItemCount() == 1
    assert widget.topLevelItem(0).text(1) == "second"


def test_any_other_cell_removes_nothing(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    scheduler.add(_due(10), "second", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")

    _click_cell(qtbot, widget, 0, 1)

    assert len(scheduler.reminders()) == 2
    assert widget.topLevelItemCount() == 2


def test_adding_and_removing_through_the_scheduler_refreshes_the_list(
    qtbot, tmp_path
):
    scheduler = _scheduler(tmp_path)
    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")
    assert widget.topLevelItemCount() == 0

    reminder = scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    assert widget.topLevelItemCount() == 1

    scheduler.remove(reminder.id)
    assert widget.topLevelItemCount() == 0


def test_the_popup_titles_itself_and_lists_one_task(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    scheduler.add(_due(10), "other", "261027 - Beta", "Beta")

    dialog = RemindersDialog(scheduler, "261027 - Alpha", "Alpha")
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Reminders - Alpha"
    assert dialog.isModal() is True
    assert dialog.reminders_list.topLevelItemCount() == 1
    assert dialog.reminders_list.topLevelItem(0).text(1) == "first"
    assert dialog.close_button.text() == "Close"
