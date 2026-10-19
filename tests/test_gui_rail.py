"""The side rail of the right pane, with Refresh on top and the pane toggle below.

The tests read the rectangles the layout hands out, so they prove where the
rail and its buttons sit, never how they look.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from mktsk.gui.window import _MARGIN
from tests.gui_helpers import directory_header, tab_labels, task_listing


def _left(widget, ancestor):
    """The left edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).x()


def _right(widget, ancestor):
    """The edge just past the right of a widget, in an ancestor's coordinates."""
    return widget.mapTo(ancestor, QPoint(widget.width(), 0)).x()


def _top(widget, ancestor):
    """The top edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).y()


def test_refresh_sits_at_the_top_of_the_rail(window):
    assert window.refresh_button.parent() is window.rail
    assert _top(window.refresh_button, window) == _top(window.rail, window)


def test_refresh_is_no_longer_the_corner_widget(window):
    assert window.tabs.cornerWidget(Qt.Corner.TopRightCorner) is not window.refresh_button


def test_the_rail_sits_to_the_left_of_the_right_pane_content(window):
    rail = window.rail

    assert _right(rail, window) <= _left(window.bottom_bar, window)
    assert _right(rail, window) <= _left(window.tabs, window)
    assert _right(rail, window) <= _left(task_listing(window), window)


def test_the_rail_shares_the_top_edge_of_the_creation_bar(window):
    assert _top(window.rail, window) == _top(window.bottom_bar, window)


def test_the_directory_header_keeps_the_top_edge_of_the_creation_bar(window):
    assert _top(directory_header(window), window) == _top(window.bottom_bar, window)


def test_refresh_still_reloads_the_listing(window, tmp_path, make_task):
    window.navigate_to(tmp_path)
    (tmp_path / "Veritas").mkdir()
    make_task(tmp_path, "260918", "Foo")

    window.refresh_button.click()

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]


def test_the_rail_width_does_not_change_when_the_window_is_resized(window):
    width = window.rail.width()

    window.resize(window.width() + 300, window.height())
    QApplication.processEvents()

    assert window.rail.width() == width


def test_the_rail_width_does_not_change_when_the_pane_is_collapsed(window):
    width = window.rail.width()

    window.splitter.setSizes([0, window.splitter.width()])
    QApplication.processEvents()

    assert window.rail.width() == width


def _bottom(widget, ancestor):
    """The bottom edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, widget.height())).y()


def test_the_toggle_sits_below_refresh_in_the_rail(window):
    assert window.toggle_button.parent() is window.rail
    assert _top(window.toggle_button, window) >= _bottom(window.refresh_button, window)


def test_clicking_the_toggle_collapses_the_left_pane(window, qtbot):
    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.splitter.sizes()[0] == 0
    assert _left(window.rail, window) == window.splitter.handleWidth()
    assert _right(window.tabs, window) == window.width() - _MARGIN
    assert _right(window.bottom_bar, window) == window.width() - _MARGIN
    assert _right(task_listing(window), window) <= window.width()


def test_clicking_the_toggle_again_restores_the_previous_width(window, qtbot):
    before = window.splitter.sizes()[0]

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.splitter.sizes()[0] == before


def test_clicking_the_toggle_after_a_drag_restores_the_pane(window, qtbot):
    initial = window.splitter.sizes()[0]

    window.splitter.setSizes([0, window.splitter.width()])
    QApplication.processEvents()

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.splitter.sizes()[0] == initial


def test_showing_the_window_again_keeps_the_split_to_restore(window, qtbot):
    initial = window.splitter.sizes()[0]
    window.splitter.setSizes([0, window.splitter.width()])

    window.hide()
    window.show()
    QApplication.processEvents()

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.splitter.sizes()[0] == initial


def test_the_toggle_tooltip_follows_the_state(window, qtbot):
    assert window.toggle_button.toolTip() == "Hide panel"

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    assert window.toggle_button.toolTip() == "Show panel"

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    assert window.toggle_button.toolTip() == "Hide panel"

    window.splitter.moveSplitter(0, 1)
    assert window.toggle_button.toolTip() == "Show panel"


def test_the_toggle_is_not_focusable(window):
    assert window.toggle_button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_refresh_stays_visible_and_works_with_the_pane_collapsed(
    window, qtbot, tmp_path, make_task
):
    window.navigate_to(tmp_path)
    make_task(tmp_path, "260918", "Foo")

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.refresh_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.splitter.sizes()[0] == 0
    assert window.refresh_button.isVisible()
    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]
