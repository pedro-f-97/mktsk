"""select_task: choosing a task row by path, and what it must not touch."""

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from mktsk.gui.tasklist import TaskListing
from mktsk.gui.taskrow import _ENTRY_ROLE
from tests.gui_helpers import (
    find_directory,
    find_task,
    select_directory,
    select_tab,
    select_task,
    task_listing,
)


def test_select_task_selects_the_row_and_scrolls_it_into_view(
    window, tmp_path, make_task, qtbot
):
    for index in range(40):
        make_task(tmp_path, "260918", f"Task{index:02d}")
    window.navigate_to(tmp_path)
    window.resize(420, 200)
    qtbot.wait(1)
    listing = task_listing(window)
    last = listing.item(listing.count() - 1)
    file = last.data(_ENTRY_ROLE).file
    visible = QRect(QPoint(0, 0), listing.viewport().size())
    listing.verticalScrollBar().setValue(0)

    assert not visible.intersects(listing.visualItemRect(last))

    assert listing.select_task(file) is True

    assert listing.currentItem() is last
    assert listing.selected_entry().file == file
    assert visible.intersects(listing.visualItemRect(last))


def test_select_task_switches_to_the_tab_holding_the_row(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    listing = task_listing(window, "Veritas")

    assert listing.select_task(file) is True

    # the row is not in the Veritas tab, so another tab had to take over
    assert window.tabs.tabText(window.tabs.currentIndex()) != "Veritas"
    assert window.tabs.currentWidget().listing.selected_entry().file == file
    assert task_listing(window).currentItem() == find_task(window, file)


def test_select_task_with_an_unknown_path_changes_nothing(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setCurrentItem(find_task(window, file))
    tab = window.tabs.currentIndex()

    result = listing.select_task(tmp_path / "260999 - Missing" / "Missing.md")

    assert result is False
    assert listing.selected_entry().file == file
    assert window.tabs.currentIndex() == tab


def test_select_task_keeps_the_destination(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)
    select_tab(window, "Veritas")
    listing = task_listing(window, "Veritas")

    assert listing.select_task(file) is True

    # the row lives in another tab, so the tab went with it
    assert window.tabs.tabText(window.tabs.currentIndex()) != "Veritas"
    assert window.creation_directory() == category
    assert window.directory_tree.currentItem() == find_directory(window, category)
    assert window.target_label.isVisible() is True


def test_select_task_makes_the_task_the_selected_entry(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    assert listing.select_task(file) is True

    entry = listing.selected_entry()
    assert entry is not None
    assert entry.file == file
    assert entry.title == "Foo"


def test_select_task_on_a_listing_without_a_window_is_false(qtbot, tmp_path):
    rows = TaskListing()
    qtbot.addWidget(rows)

    assert rows.select_task(tmp_path / "260918 - Foo" / "Foo.md") is False


def test_select_task_deferred_scroll_survives_refresh(window, tmp_path, make_task, qtbot):
    """A refresh before the deferred scroll runs does not raise."""
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    # Select the task, which schedules a deferred scroll on this listing
    assert listing.select_task(file) is True

    # Refresh the window, which rebuilds all listings and replaces items.
    # The old listing is no longer in the UI, but its deferred scroll is still pending.
    window.refresh()
    QApplication.processEvents()

    # The deferred scroll runs here (via processEvents above).
    # It calls _scroll_to_path on the old listing, which looks up the item by path.
    # Since the old listing was cleared, _item_for returns None and the scroll is skipped.
    # This exercises the `if item is not None:` branch where item is None.
    # No exception should be raised.
    # The new listing (from the refreshed tabs) has no selection.
    new_listing = task_listing(window)
    assert new_listing.selected_entry() is None


def test_scroll_to_path_on_cleared_listing_does_nothing(qapp):
    """Calling _scroll_to_path on a cleared listing exercises the empty branch."""
    import datetime
    from pathlib import Path

    from mktsk import listing
    from mktsk.gui.tasklist import TaskListing
    from mktsk.gui.taskrow import _ENTRY_ROLE

    task_list = TaskListing()
    entry = listing.TaskEntry(
        file=Path("/tmp/260918 - Foo/Foo.md"),
        title="Foo",
        date=datetime.date(2026, 9, 18),
        last_activity=datetime.date(2026, 9, 18),
        interventions=1,
        state="open",
        attachments=0,
    )
    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem()
    item.setData(_ENTRY_ROLE, entry)
    task_list.addItem(item)

    # Clear the listing
    task_list.clear()

    # Call _scroll_to_path - should not raise, item is None so branch is not taken
    task_list._scroll_to_path(entry.file)
    # If we reach here without exception, the test passes


# Escape in the task table deselects the current task.


def test_escape_deselects_the_selected_task(qtbot, window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert listing.currentItem() is None
    assert listing.action_bar.isVisible() is False


def test_escape_without_a_selection_changes_nothing(qtbot, window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert listing.currentItem() is None
    assert listing.action_bar.isVisible() is False


def test_escape_in_the_title_field_keeps_the_selection(
    qtbot, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    window.title_input.setFocus()

    qtbot.keyClick(window.title_input, Qt.Key.Key_Escape)

    assert listing.currentItem() is not None
    assert listing.action_bar.isVisible() is True


def test_escape_deselects_on_a_category_tab(qtbot, window, tmp_path, make_task):
    file = make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    listing = select_task(window, file, "Veritas")
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert listing.currentItem() is None
    assert listing.action_bar.isVisible() is False


# Focus on the task list alone never selects a task.


def _list_tasks(window, tmp_path, make_task):
    """Opens a category tab with two tasks and returns the leading file."""
    file = make_task(tmp_path / "Veritas", "260918", "Foo")
    make_task(tmp_path / "Veritas", "260917", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    return file


def _assert_nothing_selected(listing):
    assert listing.selected_entry() is None
    assert listing.action_bar.isVisible() is False
    assert listing.delegate.inset_row == -1


@pytest.mark.parametrize(
    "reason",
    [
        Qt.FocusReason.ActiveWindowFocusReason,
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
    ],
)
def test_focus_alone_selects_no_task(window, tmp_path, make_task, reason):
    _list_tasks(window, tmp_path, make_task)
    listing = task_listing(window, "Veritas")
    window.title_input.setFocus()

    listing.setFocus(reason)

    _assert_nothing_selected(listing)


def test_the_selection_survives_the_list_losing_and_regaining_focus(
    window, tmp_path, make_task
):
    file = _list_tasks(window, tmp_path, make_task)
    listing = select_task(window, file, "Veritas")

    window.title_input.setFocus()
    listing.setFocus()

    assert listing.selected_entry().file == file
    assert listing.action_bar.isVisible() is True
    assert listing.delegate.inset_row == listing.row(find_task(window, file, "Veritas"))


def test_clicking_a_row_selects_it(window, tmp_path, make_task, qtbot):
    file = _list_tasks(window, tmp_path, make_task)
    listing = task_listing(window, "Veritas")
    item = find_task(window, file, "Veritas")

    qtbot.mouseClick(
        listing.viewport(),
        Qt.MouseButton.LeftButton,
        pos=listing.visualItemRect(item).center(),
    )

    assert listing.selected_entry().file == file
    assert listing.action_bar.isVisible() is True
    assert listing.delegate.inset_row == listing.row(item)


def test_selecting_a_row_with_the_keyboard(window, tmp_path, make_task, qtbot):
    _list_tasks(window, tmp_path, make_task)
    listing = task_listing(window, "Veritas")
    listing.setFocus(Qt.FocusReason.TabFocusReason)

    qtbot.keyClick(listing, Qt.Key.Key_Down)

    assert listing.selected_entry() is not None
    assert listing.action_bar.isVisible() is True


def test_minimizing_and_restoring_selects_no_task(window, tmp_path, make_task):
    _list_tasks(window, tmp_path, make_task)
    listing = task_listing(window, "Veritas")

    window.showMinimized()
    window.showNormal()

    _assert_nothing_selected(listing)
