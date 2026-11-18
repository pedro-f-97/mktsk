"""The reminders UI: icons, row buttons, the add dialog, the list and the popup."""

import datetime
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QDate, QDateTime, QPoint, Qt, QTime
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog

from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.gui.reminders_ui import (
    AddReminderDialog,
    RemindersDialog,
    RemindersList,
)
from mktsk.gui.tree import _PATH_ROLE
from mktsk.tasks import close_task
from tests.gui_helpers import (
    action_bar,
    find_directory,
    find_task,
    select_tab,
    task_listing,
)


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


def _top_level_item(widget, row):
    item = widget.topLevelItem(row)
    assert item is not None
    return item


class _AcceptDialog:
    """Stands in for the add dialog and accepts at once."""

    def __init__(self, task_title, parent=None):
        self.task_title = task_title

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Accepted

    def due(self):
        return _due(12)

    def message(self):
        return "note"


class _RejectDialog(_AcceptDialog):
    """Stands in for the add dialog and cancels at once."""

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Rejected


def test_the_row_bar_offers_the_reminders_button_for_an_open_task(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    reminders = bar.reminder_buttons()
    assert len(reminders) == 1
    assert reminders[0] is bar.reminders_button
    assert bar.reminders_button.toolTip() == "Reminders"
    assert bar.reminders_button.text() == ""
    assert bar.reminders_button.isVisible() is True
    assert bar.reminders_button.iconSize() == bar.open_button.iconSize()
    assert bar.reminders_button.autoRaise() is True
    actions = bar.reminders_menu.actions()
    assert [action.text() for action in actions] == ["Add reminder...", "Reminders..."]


def test_the_row_bar_offers_no_reminders_without_a_scheduler(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]


def test_the_closed_tab_offers_no_reminder_buttons(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    close_task(file.parent, "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    select_tab(window, "Closed")
    bar = action_bar(window, tmp_path / "261027 - Teste.zip", "Closed")

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]


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

    action_bar(window, file).reminders_menu.actions()[0].trigger()

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

    action_bar(window, file).reminders_menu.actions()[0].trigger()

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

    action_bar(window, file).reminders_menu.actions()[1].trigger()

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
    assert [_top_level_item(widget, row).text(1) for row in range(2)] == [
        "first",
        "second",
    ]
    assert _top_level_item(widget, 0).text(0) == "27/10/2026 09:00"


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
    assert [_top_level_item(widget, row).text(2) for row in range(3)] == [
        "Alpha",
        "Beta",
        "Alpha",
    ]


def test_a_reminder_without_a_message_shows_its_title(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "", "261027 - Alpha", "Alpha")

    widget = _shown_list(qtbot, scheduler, "261027 - Alpha")

    assert _top_level_item(widget, 0).text(1) == "Alpha"


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
    assert _top_level_item(widget, 0).text(1) == "second"


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
    assert _top_level_item(dialog.reminders_list, 0).text(1) == "first"
    assert dialog.close_button.text() == "Close"


# The single reminders dropdown button of the action bar.


class _AcceptReminderDialog:
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
    monkeypatch.setattr("mktsk.gui.tasklist.AddReminderDialog", _AcceptReminderDialog)

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


# The reminders panel, its bell toggle and the rows of the reminders list.


def _panel_list(qtbot, scheduler, resolver=None):
    widget = RemindersList(scheduler, resolver=resolver)
    qtbot.addWidget(widget)
    widget.resize(480, 240)
    widget.show()
    return widget


def _attach(window, tmp_path):
    scheduler = _scheduler(tmp_path)
    window.attach_reminder_scheduler(scheduler)
    return scheduler


def test_a_click_outside_the_delete_cell_reports_the_task(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _panel_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == ["261027 - Alpha"]
    assert len(scheduler.reminders()) == 1


def test_the_delete_cell_removes_the_reminder_and_reports_nothing(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _panel_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    _click_cell(qtbot, widget, 0, widget.columnCount() - 1)

    assert clicked == []
    assert scheduler.reminders() == []


def test_a_row_whose_task_is_gone_is_dimmed_and_reports_nothing(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _panel_list(qtbot, scheduler, resolver=lambda task: None)
    clicked = []
    widget.task_clicked.connect(clicked.append)
    dim = widget.palette().color(QPalette.ColorRole.PlaceholderText)

    row = _top_level_item(widget, 0)
    assert row.foreground(1).color() == dim

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == []


def test_a_row_without_a_resolver_is_not_dimmed(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _panel_list(qtbot, scheduler)
    clicked = []
    widget.task_clicked.connect(clicked.append)

    assert _top_level_item(widget, 0).foreground(1).style() == Qt.BrushStyle.NoBrush

    _click_cell(qtbot, widget, 0, 1)

    assert clicked == ["261027 - Alpha"]


def test_a_resolved_row_is_not_dimmed(qtbot, tmp_path):
    scheduler = _scheduler(tmp_path)
    scheduler.add(_due(9), "first", "261027 - Alpha", "Alpha")
    widget = _panel_list(
        qtbot, scheduler, resolver=lambda task: Path(tmp_path) / "task.md"
    )

    assert _top_level_item(widget, 0).foreground(1).style() == Qt.BrushStyle.NoBrush


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
