"""The reminders panel, its bell toggle and the rows of the reminders list."""

import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette

from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.gui.reminders_ui import RemindersList
from mktsk.gui.tree import _PATH_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import find_directory, find_task


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


def _attach(window, tmp_path):
    scheduler = _scheduler(tmp_path)
    window.attach_reminder_scheduler(scheduler)
    return scheduler


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


def test_bell_hidden_until_scheduler_attached(window, tmp_path):
    assert window.directory_tree.bell_button.isVisible() is False
    assert window.reminder_scheduler is None
    # no panel yet: toggling is a defensive no-op
    window._toggle_reminders(True)
    window._toggle_reminders(False)

    _attach(window, tmp_path)

    assert window.directory_tree.bell_button.isVisible() is True
    assert window.reminder_scheduler is not None


def test_toggle_shows_and_hides_reminders_panel(window, tmp_path, qtbot):
    _attach(window, tmp_path)
    bell = window.directory_tree.bell_button

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)

    assert window.directory_stack.currentWidget() is window.reminders_panel
    assert window.directory_tree.headerItem().text(0) == "Reminders"
    assert window.choose_button.isVisible() is False
    assert window.up_button.isVisible() is False
    assert window.directory_tree.header_button.isVisible() is False
    assert bell.isVisible() is True

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)

    assert window.directory_stack.currentWidget() is window.directory_tree
    assert window.directory_tree.headerItem().text(0) == "Directory"
    assert window.choose_button.isVisible() is True
    assert window.up_button.isVisible() is True
    assert window.directory_tree.header_button.isVisible() is True


def test_toggle_keeps_tree_selection_and_destination(window, tmp_path, qtbot):
    category = (tmp_path / "cat").resolve()
    category.mkdir()
    window.navigate_to(tmp_path)
    window.directory_tree.setCurrentItem(find_directory(window, category))
    before = window.target_label.text()

    _attach(window, tmp_path)
    bell = window.directory_tree.bell_button
    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)

    assert window.directory_stack.currentWidget() is window.directory_tree
    selected = window.directory_tree.currentItem()
    assert selected.data(0, _PATH_ROLE) == str(category)
    assert window.target_label.text() == before


def test_search_panel_visible_in_both_modes(window, tmp_path, qtbot):
    _attach(window, tmp_path)
    assert window.search_panel.isVisible() is True

    bell = window.directory_tree.bell_button
    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.search_panel.isVisible() is True

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.search_panel.isVisible() is True


def test_starts_in_directory_mode_with_no_reminders_settings_key(window):
    assert window.directory_stack.currentWidget() is window.directory_tree
    assert window.directory_tree.headerItem().text(0) == "Directory"
    assert not any("reminders" in key for key in window.settings.allKeys())


def test_collapse_and_restore_keeps_reminders_mode(window, tmp_path, qtbot):
    _attach(window, tmp_path)
    bell = window.directory_tree.bell_button
    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.directory_stack.currentWidget() is window.reminders_panel

    window.toggle_left_pane()
    window.toggle_left_pane()

    assert window.directory_stack.currentWidget() is window.reminders_panel


def test_panel_refreshes_when_shown_and_when_changed(window, tmp_path, qtbot):
    scheduler = _attach(window, tmp_path)
    bell = window.directory_tree.bell_button

    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    assert window.reminders_list.topLevelItemCount() == 1

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.reminders_list.topLevelItemCount() == 1

    scheduler.add(_due(10), "second", "261027 - Alpha", "Alpha")
    assert window.reminders_list.topLevelItemCount() == 2


def test_resolver_finds_open_task_archived_task_and_unknown(window, tmp_path, make_task):
    open_file = make_task(tmp_path, "261027", "Alpha")
    archived_folder = tmp_path / "260918 - Beta"
    make_task(archived_folder.parent, "260918", "Beta")
    close_task(archived_folder, "Beta")
    archived_file = tmp_path / "260918 - Beta.zip"

    window.navigate_to(tmp_path)
    window.refresh()

    resolver = window._resolve_reminder_task
    assert resolver("261027 - Alpha") == open_file
    assert resolver("260918 - Beta") == archived_file
    assert resolver("261027 - Nobody") is None


def test_clicking_reminder_selects_open_task(window, tmp_path, make_task, qtbot):
    make_task(tmp_path, "261027", "Alpha")
    window.navigate_to(tmp_path)
    _attach(window, tmp_path)
    bell = window.directory_tree.bell_button

    # an unknown reminder task resolves to nothing and selects nothing
    window._select_reminder_task("does not exist")

    scheduler = window.reminder_scheduler
    scheduler.add(_due(9), "note", "261027 - Alpha", "Alpha")
    before = window.target_label.text()

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.directory_stack.currentWidget() is window.reminders_panel

    _click_cell(qtbot, window.reminders_list, 0, 1)

    found = find_task(window, tmp_path / "261027 - Alpha" / "Alpha.md")
    assert found is not None
    assert window.target_label.text() == before


def test_clicking_reminder_selects_archived_task(window, tmp_path, make_task, qtbot):
    make_task(tmp_path, "261027", "Alpha")
    window.navigate_to(tmp_path)
    close_task(tmp_path / "261027 - Alpha", "Alpha")
    window.refresh()
    _attach(window, tmp_path)
    bell = window.directory_tree.bell_button

    scheduler = window.reminder_scheduler
    scheduler.add(_due(9), "note", "261027 - Alpha", "Alpha")
    before = window.target_label.text()

    qtbot.mouseClick(bell, Qt.MouseButton.LeftButton)
    assert window.directory_stack.currentWidget() is window.reminders_panel

    _click_cell(qtbot, window.reminders_list, 0, 1)

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Closed"
    found = find_task(window, tmp_path / "261027 - Alpha.zip", "Closed")
    assert found is not None
    assert window.target_label.text() == before
