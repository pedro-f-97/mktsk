"""The geometry of the two panes of the main window.

The tests read the rectangles the layout hands out, so they prove where a
control sits and which pane it belongs to, never how it looks.
"""

from freezegun import freeze_time
from PySide6.QtCore import QPoint, Qt

from mktsk.gui.window import _MARGIN
from tests.gui_helpers import tab_labels, tree_child_labels


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


def test_the_path_row_holds_only_the_path_label(window):
    assert window.path_row.parent() is window.left_panel
    assert window.path_label.parent() is window.path_row


def test_the_header_holds_choose_and_up(window):
    header = window.directory_tree.header()

    assert window.choose_button.parent() is header
    assert window.up_button.parent() is header


def test_choose_and_up_sit_to_the_left_of_the_category_button(window):
    header = window.directory_tree.header()
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
    header = window.directory_tree.header()
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


def test_the_path_is_elided_in_the_room_the_row_has(window):
    assert window.path_label.text() != str(window.current_directory)
    assert "\u2026" in window.path_label.text()


def test_refresh_is_the_corner_widget_of_the_tab_bar(window):
    assert window.tabs.cornerWidget(Qt.Corner.TopRightCorner) is window.refresh_button


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
    header = window.directory_tree.header()
    category = window.directory_tree.header_button

    for button in (window.choose_button, window.up_button, category):
        assert button.size() == category.size()
        assert button.y() == (header.height() - button.height()) // 2


def test_the_header_buttons_are_ordered_and_do_not_overlap(window):
    header = window.directory_tree.header()
    choose = window.choose_button
    up = window.up_button
    category = window.directory_tree.header_button

    assert _left(choose, header) < _right(choose, header) <= _left(up, header)
    assert _left(up, header) < _right(up, header) <= _left(category, header)


def test_the_path_label_fills_the_path_row(window):
    assert window.path_label.width() == window.path_row.width()


def test_the_path_row_lines_up_with_the_tab_bar(window):
    tab_bar = window.tabs.tabBar()

    assert _left(window.path_row, window) == _MARGIN
    assert _top(window.path_row, window) == _top(tab_bar, window)
    assert window.path_row.height() == tab_bar.height()


def test_the_outer_edges_keep_the_window_margin(window):
    assert _left(window.path_row, window.left_panel) == _MARGIN
    assert window.right_panel.width() - _right(window.tabs, window.right_panel) == _MARGIN
    assert (
        window.right_panel.width() - _right(window.bottom_bar, window.right_panel)
        == _MARGIN
    )


def test_the_panes_are_separated_by_the_handle_alone(window):
    gap = _left(window.tabs, window) - _right(window.directory_tree, window)

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
