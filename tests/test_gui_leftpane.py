"""The left pane as one unit: the Directory header, the path and the tree.

The tests read the rectangles the layout hands out, so they prove where a
control sits, never how it looks.
"""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionHeader

from mktsk.gui.tree import _HEADER_BUTTON_MARGIN
from mktsk.gui.window import _MARGIN
from tests.gui_helpers import directory_header


def _left(widget, ancestor):
    """The left edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).x()


def _right(widget, ancestor):
    """The edge just past the right of a widget, in an ancestor's coordinates."""
    return widget.mapTo(ancestor, QPoint(widget.width(), 0)).x()


def _top(widget, ancestor):
    """The top edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).y()


def _bottom(widget, ancestor):
    """The bottom edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, widget.height())).y()


def _header_text_left(header):
    """The left padding the header gives its title, read from the style."""
    option = QStyleOptionHeader()
    option.rect = header.rect()
    option.section = 0
    option.state = QStyle.StateFlag.State_Enabled
    label = header.style().subElementRect(
        QStyle.SubElement.SE_HeaderLabel, option, header
    )
    return label.left()


def _give_the_path_room(window, room):
    """Widens the window to hold the room and sizes the left pane to it."""
    window.resize(window.width() + room + 200, window.height())
    QApplication.processEvents()
    window.splitter.setSizes([room, window.splitter.width() - room])
    window._update_path_label()


def test_the_left_pane_stacks_the_header_the_path_and_the_tree(window):
    header = directory_header(window)
    path = window.path_row
    tree = window.directory_tree

    assert header.parent() is window.left_panel
    assert _top(header, window) < _top(path, window) < _top(tree, window)


def test_the_rows_of_the_left_pane_do_not_overlap(window):
    header = directory_header(window)
    path = window.path_row
    tree = window.directory_tree

    assert _bottom(header, window) <= _top(path, window)
    assert _bottom(path, window) <= _top(tree, window)


def test_the_rows_are_no_further_apart_than_the_margin(window):
    header = directory_header(window)
    path = window.path_row
    tree = window.directory_tree

    assert _top(path, window) - _bottom(header, window) <= _MARGIN
    assert _top(tree, window) - _bottom(path, window) <= _MARGIN


def test_the_path_sits_below_the_directory_header(window):
    header = directory_header(window)

    assert _top(window.path_label, window) >= _bottom(header, window)
    assert _top(window.path_label, window) > _top(header, window)


def test_the_path_label_lines_up_with_the_header_text(window):
    assert window.path_label.contentsMargins().left() == _header_text_left(
        directory_header(window)
    )


def test_the_header_lines_up_with_the_tab_bar(window):
    header = directory_header(window)
    tab_bar = window.tabs.tabBar()

    assert _top(header, window) == _top(tab_bar, window)
    assert header.height() == tab_bar.height()


def test_the_three_buttons_sit_inside_the_header_in_order(window):
    header = directory_header(window)
    choose = window.choose_button
    up = window.up_button
    plus = window.directory_tree.header_button

    for button in (choose, up, plus):
        assert button.parent() is header
    assert _left(choose, header) < _right(choose, header) <= _left(up, header)
    assert _left(up, header) < _right(up, header) <= _left(plus, header)
    assert plus.x() == max(choose.x(), up.x(), plus.x())


def test_the_category_button_sits_at_the_right_end_of_the_header(window):
    header = directory_header(window)
    plus = window.directory_tree.header_button

    assert header.width() - _right(plus, header) == _HEADER_BUTTON_MARGIN


def test_the_header_buttons_stay_clear_at_a_narrow_width(window):
    window.splitter.setSizes([1, window.splitter.width()])
    QApplication.processEvents()
    header = directory_header(window)
    text_width = header.fontMetrics().horizontalAdvance("Directory")

    for button in (
        window.choose_button,
        window.up_button,
        window.directory_tree.header_button,
    ):
        assert _left(button, header) >= text_width
        assert _right(button, header) <= header.width()


def test_the_tree_has_no_visible_header(window):
    assert window.directory_tree.isHeaderHidden() is True


def test_the_path_is_elided_when_the_pane_is_narrow(window, tmp_path):
    directory = tmp_path / ("a-long-category-name" * 4)
    directory.mkdir()
    window.navigate_to(directory)
    full = str(window.current_directory)
    room = window.path_label.fontMetrics().horizontalAdvance(full) // 2

    _give_the_path_room(window, room)

    assert window.path_label.text() != full
    assert "\u2026" in window.path_label.text()
    assert len(window.path_label.text()) < len(full)


def test_the_path_is_shown_in_full_when_the_pane_is_wide(window, tmp_path):
    window.navigate_to(tmp_path)
    full = str(window.current_directory)
    room = window.path_label.fontMetrics().horizontalAdvance(full) + 2 * _MARGIN

    _give_the_path_room(window, room)

    assert window.path_label.text() == full
    assert "\u2026" not in window.path_label.text()


def test_the_outer_margins_and_the_gap_are_unchanged(window):
    header = directory_header(window)

    assert _left(header, window.left_panel) == _MARGIN
    assert window.right_panel.width() - _right(window.tabs, window.right_panel) == _MARGIN
    gap = _left(window.tabs, window) - _right(window.directory_tree, window)
    assert gap == window.splitter.handleWidth()
