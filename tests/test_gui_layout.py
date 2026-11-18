"""The geometry of the two panes of the main window.

The tests read the rectangles the layout hands out, so they prove where a
control sits and which pane it belongs to, never how it looks.
"""

from freezegun import freeze_time
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionHeader

from mktsk.gui.tree import _HEADER_BUTTON_MARGIN
from mktsk.gui.window import _MARGIN
from tests.gui_helpers import (
    directory_header,
    tab_labels,
    task_listing,
    tree_child_labels,
)


def _left(widget, ancestor):
    """The left edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).x()


def _right(widget, ancestor):
    """The edge just past the right of a widget, in an ancestor's coordinates."""
    return widget.mapTo(ancestor, QPoint(widget.width(), 0)).x()


def _top(widget, ancestor):
    """The top edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).y()


def _focus_order(window):
    """The focusable controls, in the order Tab walks them."""
    named = {
        window.choose_button: "choose",
        window.up_button: "up",
        window.refresh_button: "refresh",
        window.directory_tree: "tree",
        window.tabs: "tabs",
        window.title_input: "title",
        window.create_button: "create",
    }
    order = []
    node = window.choose_button
    while True:
        node = node.nextInFocusChain()
        if node is window.choose_button:
            break
        if node in named:
            order.append(named[node])
    return order


def _give_the_path_room(window, room):
    """Widens the window to hold the room and sizes the path row to it."""
    window.resize(window.width() + room + 200, window.height())
    QApplication.processEvents()
    window.splitter.setSizes([room, window.splitter.width() - room])
    window._update_path_label()


def test_the_path_row_holds_only_the_path_label(window):
    assert window.path_row.parent() is window.left_panel
    assert window.path_label.parent() is window.path_row


def test_the_header_holds_choose_and_up(window):
    header = directory_header(window)

    assert window.choose_button.parent() is header
    assert window.up_button.parent() is header


def test_choose_and_up_sit_to_the_left_of_the_category_button(window):
    header = directory_header(window)
    choose = window.choose_button
    up = window.up_button

    assert up.y() == choose.y()
    assert _left(choose, header) < _left(up, header)
    assert _right(choose, header) <= _left(up, header)


def test_the_path_sits_above_the_tree(window):
    assert _left(window.path_row, window) == _left(window.directory_tree, window)
    assert window.path_row.geometry().bottom() < window.directory_tree.geometry().top()


def test_the_header_buttons_stay_inside_a_narrow_header(window):
    window.splitter.setSizes([1, window.splitter.width()])
    header = directory_header(window)
    text_width = header.fontMetrics().horizontalAdvance(
        window.directory_tree.headerItem().text(0)
    )

    for button in (
        window.choose_button,
        window.up_button,
        window.directory_tree.header_button,
    ):
        assert _left(button, header) >= text_width
        assert _right(button, header) <= header.width()


def test_the_path_is_elided_in_the_room_the_row_has(window, tmp_path):
    directory = tmp_path / ("a-long-category-name" * 4)
    directory.mkdir()
    window.navigate_to(directory)
    full = str(window.current_directory)
    room = window.path_label.fontMetrics().horizontalAdvance(full) // 2

    _give_the_path_room(window, room)

    assert window.path_label.text() != full
    assert "\u2026" in window.path_label.text()
    assert len(window.path_label.text()) < len(full)


def test_the_path_is_shown_in_full_when_the_row_has_the_room(window, tmp_path):
    window.navigate_to(tmp_path)
    full = str(window.current_directory)
    room = window.path_label.fontMetrics().horizontalAdvance(full) + 2 * _MARGIN

    _give_the_path_room(window, room)

    assert window.path_label.text() == full
    assert "\u2026" not in window.path_label.text()


def test_refresh_is_the_corner_widget_of_the_tab_bar(window):
    assert window.refresh_button.parent() is window.rail
    assert _top(window.refresh_button, window) == _top(window.rail, window)


def test_refresh_reloads_both_the_tree_and_the_lists(window, tmp_path, make_task):
    window.navigate_to(tmp_path)
    (tmp_path / "Veritas").mkdir()
    make_task(tmp_path, "260918", "Foo")

    window.refresh_button.click()

    assert tree_child_labels(window) == ["Veritas"]
    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]


def test_the_bottom_bar_stays_in_the_right_panel(window):
    assert window.bottom_bar.parent() is window.right_panel
    assert _left(window.bottom_bar, window) >= _right(window.left_panel, window)


def test_the_title_field_fills_the_bottom_bar(window):
    title = window.title_input
    create = window.create_button

    assert _left(title, window.bottom_bar) == 0
    assert title.width() > create.width()
    assert _right(title, window.bottom_bar) <= _left(create, window.bottom_bar)
    assert _right(create, window.bottom_bar) == window.bottom_bar.width()


def test_the_header_buttons_have_the_size_and_centre_of_the_category_button(window):
    header = directory_header(window)
    category = window.directory_tree.header_button

    for button in (window.choose_button, window.up_button, category):
        assert button.size() == category.size()
        assert button.y() == (header.height() - button.height()) // 2


def test_the_header_buttons_are_ordered_and_do_not_overlap(window):
    header = directory_header(window)
    choose = window.choose_button
    up = window.up_button
    category = window.directory_tree.header_button

    assert _left(choose, header) < _right(choose, header) <= _left(up, header)
    assert _left(up, header) < _right(up, header) <= _left(category, header)


def test_the_path_label_fills_the_path_row(window):
    assert window.path_label.width() == window.path_row.width()


def test_the_header_row_lines_up_with_the_creation_bar(window):
    header = directory_header(window)
    tab_bar = window.tabs.tabBar()

    assert _left(header, window) == _MARGIN
    assert _top(header, window) == _top(window.bottom_bar, window)
    assert header.height() == tab_bar.height()


def test_the_outer_edges_keep_the_window_margin(window):
    assert _left(window.path_row, window.left_panel) == _MARGIN
    assert window.right_panel.width() - _right(window.tabs, window.right_panel) == _MARGIN
    assert (
        window.right_panel.width() - _right(window.bottom_bar, window.right_panel)
        == _MARGIN
    )


def test_the_panes_are_separated_by_the_handle_alone(window):
    gap = _left(window.rail, window) - _right(window.directory_tree, window)

    assert gap == window.splitter.handleWidth()


def test_the_tab_order_is_unchanged(window):
    assert _focus_order(window) == [
        "up",
        "refresh",
        "tree",
        "tabs",
        "title",
        "create",
    ]


@freeze_time("2026-09-30")
def test_enter_in_the_title_field_still_creates_the_task(
    window, qtbot, tmp_path, fake_open
):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Test Task")

    qtbot.keyClick(window.title_input, Qt.Key.Key_Return)

    assert (tmp_path / "260930 - TestTask" / "TestTask.md").is_file()
    assert window.title_input.text() == ""


# The left pane as one unit: the Directory header, the path and the tree.
#
# The tests read the rectangles the layout hands out, so they prove where a
# control sits, never how it looks.


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


def _widen_the_left_pane(window, room):
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


def test_the_header_lines_up_with_the_creation_bar(window):
    header = directory_header(window)
    tab_bar = window.tabs.tabBar()

    assert _top(header, window) == _top(window.bottom_bar, window)
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

    _widen_the_left_pane(window, room)

    assert window.path_label.text() != full
    assert "\u2026" in window.path_label.text()
    assert len(window.path_label.text()) < len(full)


def test_the_path_is_shown_in_full_when_the_pane_is_wide(window, tmp_path):
    window.navigate_to(tmp_path)
    full = str(window.current_directory)
    room = window.path_label.fontMetrics().horizontalAdvance(full) + 2 * _MARGIN

    _widen_the_left_pane(window, room)

    assert window.path_label.text() == full
    assert "\u2026" not in window.path_label.text()


def test_the_outer_margins_and_the_gap_are_unchanged(window):
    header = directory_header(window)

    assert _left(header, window.left_panel) == _MARGIN
    assert window.right_panel.width() - _right(window.tabs, window.right_panel) == _MARGIN
    gap = _left(window.rail, window) - _right(window.directory_tree, window)
    assert gap == window.splitter.handleWidth()


def _path_label_pixel(window):
    label = window.path_label
    image = label.grab().toImage()
    return image.pixelColor(label.width() - 2, label.height() // 2)


def test_the_path_label_takes_the_background_of_the_tree(window, qapp):
    original = qapp.palette()

    try:
        for base, window_colour in (
            ("#ffffff", "#f0f0f0"),
            ("#101010", "#202020"),
        ):
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Base, QColor(base))
            palette.setColor(QPalette.ColorRole.Window, QColor(window_colour))
            qapp.setPalette(palette)
            QApplication.processEvents()

            tree_base = window.directory_tree.viewport().palette().color(
                QPalette.ColorRole.Base
            )
            assert _path_label_pixel(window) == tree_base
    finally:
        qapp.setPalette(original)


# The side rail of the right pane, with Refresh on top and the pane toggle below.
#
# The tests read the rectangles the layout hands out, so they prove where the
# rail and its buttons sit, never how they look.


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
