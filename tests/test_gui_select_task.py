"""select_task: choosing a task row by path, and what it must not touch."""

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from mktsk.gui.tasklist import _ENTRY_ROLE, TaskListing
from tests.gui_helpers import (
    find_directory,
    find_task,
    select_directory,
    select_tab,
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
    from mktsk.gui.tasklist import _ENTRY_ROLE, TaskListing

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
