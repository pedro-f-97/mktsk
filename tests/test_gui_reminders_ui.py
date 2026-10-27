"""The reminders UI: icons, row buttons, the add dialog, the list and the popup."""

import datetime

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor

from mktsk.gui.icons import _draw_bell, _draw_bell_plus, _stroked_icon
from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.gui.reminders_ui import RemindersList


class _FakeTray:
    """Records nothing: the tests never reach a notification."""

    def notify(self, title, message):
        pass


def _scheduler(tmp_path):
    return ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")


def _due(hour, minute=0, day=27):
    return datetime.datetime(2026, 10, day, hour, minute)  # noqa: DTZ001


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


def test_both_bell_icons_draw_at_several_sizes(qapp):
    for draw in (_draw_bell, _draw_bell_plus):
        icon = _stroked_icon(QColor("#000000"), draw)
        assert icon.isNull() is False
        for size in (12, 16, 18, 24):
            assert icon.pixmap(QSize(size, size)).isNull() is False


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
