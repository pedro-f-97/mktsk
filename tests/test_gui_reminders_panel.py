"""The reminders panel, its bell toggle and the rows of the reminders list."""

import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette

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


def _shown_list(qtbot, scheduler, resolver=None):
    widget = RemindersList(scheduler, resolver=resolver)
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


def test_a_click_outside_the_delete_cell_reports_the_task(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == ["261027 - Alpha"]
    assert len(scheduler.reminders()) == 1


def test_the_delete_cell_removes_the_reminder_and_reports_nothing(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    _click_cell(qtbot, widget, 0, widget.columnCount() - 1)

    assert clicked == []
    assert scheduler.reminders() == []


def test_a_row_whose_task_is_gone_is_dimmed_and_reports_nothing(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler, resolver=lambda task: None)
    clicked = []
    widget.task_clicked.connect(clicked.append)
    dim = widget.palette().color(QPalette.ColorRole.PlaceholderText)

    row = widget.topLevelItem(0)
    assert row.foreground(1).color() == dim

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == []


def test_a_row_without_a_resolver_is_not_dimmed(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _shown_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    assert widget.topLevelItem(0).foreground(1).style() == Qt.BrushStyle.NoBrush

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == ["261027 - Alpha"]


def test_a_resolved_row_is_not_dimmed(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _shown_list(
        qtbot, scheduler, resolver=lambda task: Path(tmp_path) / "task.md"
    )

    assert widget.topLevelItem(0).foreground(1).style() == Qt.BrushStyle.NoBrush
