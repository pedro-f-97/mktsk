"""Focus on the task list alone never selects a task."""

import pytest
from PySide6.QtCore import Qt

from tests.gui_helpers import find_task, select_tab, select_task, task_listing


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
