"""Escape in the task table deselects the current task."""

from PySide6.QtCore import Qt

from tests.gui_helpers import (
    select_tab,
    select_task,
    task_listing,
)


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
