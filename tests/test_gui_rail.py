"""The side rail of the right pane, with Refresh on top and the pane toggle below.

The tests read the rectangles the layout hands out, so they prove where the
rail and its buttons sit, never how they look.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

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
