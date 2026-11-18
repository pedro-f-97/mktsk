"""Tests for the unified selection delegate with empty text."""

from collections import Counter

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionViewItem,
)

from mktsk.gui.selection import (
    _ROW_LINE_REACH,
    _SELECTION_INDICATOR_GAP,
    _SELECTION_INDICATOR_WIDTH,
    _contrast_ratio,
    _selection_tint,
    _UnifiedSelectionDelegate,
)
from tests.gui_helpers import (
    find_directory,
    render_row,
    row_background,
)


def _render_row(view, item, state, background):
    """Renders one row offscreen, over a given background."""
    rect = QRect(view.visualItemRect(item))
    image = QImage(rect.size(), QImage.Format.Format_RGB32)
    image.fill(background)
    index = view.indexFromItem(item)
    delegate = view.itemDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, index)
    option.rect = QRect(0, 0, rect.width(), rect.height())
    option.state = state
    option.palette = view.viewport().palette()
    option.widget = view
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()
    return image


_SELECTED_ACTIVE = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)


def test_selected_item_with_empty_text_renders_without_crash(qapp):
    """A selected item with empty display text paints the selection without drawing text."""
    # Create a list widget with the unified selection delegate
    list_widget = QListWidget()
    list_widget.setItemDelegate(_UnifiedSelectionDelegate(list_widget))

    # Add an item with empty text
    item = QListWidgetItem("")
    list_widget.addItem(item)

    # Select the item
    list_widget.setCurrentItem(item)
    list_widget.resize(200, 50)
    list_widget.show()

    # Render the selected row - this exercises the `if text:` branch where text is empty
    base = list_widget.viewport().palette().color(QPalette.ColorRole.Base)
    image = _render_row(list_widget, item, _SELECTED_ACTIVE, base)

    # The selection tint should be painted (rail and bracket lines)
    # even though there's no text to draw
    highlight = list_widget.viewport().palette().color(QPalette.ColorRole.Highlight)

    # Check that the rail is painted at the left edge
    rail_pixels = [
        image.pixelColor(x, image.height() // 2).rgb()
        for x in range(4)  # _SELECTION_INDICATOR_WIDTH = 4
    ]
    assert all(colour == highlight.rgb() for colour in rail_pixels), (
        "Selection rail should be painted even with empty text"
    )

    # The tint should fill the rest of the row
    tint_colour = image.pixelColor(10, image.height() // 2)
    assert tint_colour != highlight, "Tint should be different from highlight"
    assert tint_colour != QColor(base), "Tint should be different from base"


def test_selected_item_with_empty_text_in_tree_renders_without_crash(qapp):
    """A selected tree item with empty display text paints the selection without drawing text."""
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.setItemDelegate(_UnifiedSelectionDelegate(tree, rail_at_left_edge=True))

    # Add an item with empty text
    item = QTreeWidgetItem([""])
    tree.addTopLevelItem(item)

    # Select the item
    tree.setCurrentItem(item)
    tree.resize(200, 50)
    tree.show()

    # Render the selected row
    base = tree.viewport().palette().color(QPalette.ColorRole.Base)
    image = _render_row(tree, item, _SELECTED_ACTIVE, base)

    # The selection rail should be painted at the left edge (rail_at_left_edge=True)
    highlight = tree.viewport().palette().color(QPalette.ColorRole.Highlight)
    rail_pixels = [
        image.pixelColor(x, image.height() // 2).rgb()
        for x in range(4)  # _SELECTION_INDICATOR_WIDTH = 4
    ]
    assert all(colour == highlight.rgb() for colour in rail_pixels), (
        "Selection rail should be painted at left edge even with empty text"
    )


# Regression tests for the selection indicator of the directory tree.
#
# `QTreeView` paints the part of a selected row that lies before its items
# itself, through `PE_PanelItemViewRow`, before the item delegate sees the row.
# Clearing `State_Selected` inside the delegate cannot remove that native fill:
# it stayed behind the custom `[` outline, and the outline sat at the item's text
# origin rather than where the native bar was, at the left edge of the row.


# the outline has to leave the text clear of the rail, at least as far as the
# bracket lines reach past it
_MINIMUM_TEXT_GAP = _ROW_LINE_REACH

_STYLES = tuple(QStyleFactory.keys())


@pytest.fixture(params=_STYLES)
def styled(request, qapp):
    """Sets a style on the application before the window is built."""
    original = qapp.style().objectName()
    style = QStyleFactory.create(request.param)
    if style is None:
        pytest.skip(f"{request.param} cannot be created")
    qapp.setStyle(style)
    yield request.param
    restored = QStyleFactory.create(original)
    if restored is not None:
        qapp.setStyle(restored)


def _select_row(window, qapp, tmp_path):
    """Selects a directory row and returns the tree and the row."""
    (tmp_path / "Reports").mkdir()
    (tmp_path / "Projects").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")
    tree.setCurrentItem(item)
    tree.setFocus()
    qapp.processEvents()
    return tree, item


def _viewport_image(tree):
    """Renders the real viewport, including the row around the delegate."""
    image = QImage(tree.viewport().size(), QImage.Format.Format_RGB32)
    image.fill(tree.viewport().palette().color(QPalette.ColorRole.Base))
    tree.viewport().render(image)
    return image


def _highlight_columns(image, row, highlight):
    """The columns of the highlight colour on the middle line of a row."""
    y = row.center().y()
    return [
        x for x in range(image.width()) if image.pixelColor(x, y) == highlight
    ]


def _row_background(image, row):
    """The colour most of the item area is made of, which is its background."""
    counts = Counter(
        image.pixelColor(x, y).rgb()
        for y in range(max(row.top(), 0), min(row.bottom() + 1, image.height()))
        for x in range(max(row.left(), 0), image.width())
    )
    return QColor(counts.most_common(1)[0][0])


def _first_text_column(image, row, background):
    """The first column of the item area whose ink reads against the background."""
    for x in range(max(row.left(), 0), image.width()):
        colour = image.pixelColor(x, row.center().y())
        if _contrast_ratio(colour, background) >= 4.5:
            return x
    return None


def test_directory_tree_selected_row_has_one_indicator_at_the_left_edge(
    styled, window, tmp_path, qapp
):
    """The custom rail is the only indicator, where the native bar used to be."""
    tree, item = _select_row(window, qapp, tmp_path)
    row = tree.visualItemRect(item)
    palette = tree.viewport().palette()
    highlight = palette.color(QPalette.ColorRole.Highlight)

    image = _viewport_image(tree)
    painted = _highlight_columns(image, row, highlight)

    assert painted == list(range(_SELECTION_INDICATOR_WIDTH)), (
        f"expected only the custom rail in columns 0-"
        f"{_SELECTION_INDICATOR_WIDTH - 1}, found highlight in {painted}. "
        "A native indicator left of the rail, or a rail away from the left "
        "edge, means the tree still paints its own selection."
    )

    # the band the native panel used to fill carries the same 25% tint as the
    # item area, not a second selection colour
    background = _row_background(image, row)
    band = image.pixelColor(_SELECTION_INDICATOR_WIDTH + 1, row.center().y())
    assert band == background, (
        f"the row band left of the item is {band.name()}, expected the "
        f"selection tint {background.name()}"
    )


def test_directory_tree_selected_row_separates_outline_from_text(
    styled, window, tmp_path, qapp
):
    """The text starts after the outline, leaving a clear gap."""
    tree, item = _select_row(window, qapp, tmp_path)
    row = tree.visualItemRect(item)
    palette = tree.viewport().palette()
    highlight = palette.color(QPalette.ColorRole.Highlight)

    image = _viewport_image(tree)
    painted = _highlight_columns(image, row, highlight)
    assert painted, "the selected row painted no indicator"
    rail_end = max(painted) + 1

    background = _row_background(image, row)
    first_text = _first_text_column(image, row, background)

    assert first_text is not None, "no text found on the selected row"
    gap = first_text - rail_end
    assert gap >= _MINIMUM_TEXT_GAP, (
        f"text starts at x={first_text}, {gap} px after the outline ends at "
        f"x={rail_end}; expected at least {_MINIMUM_TEXT_GAP} px, the room the "
        f"bracket lines take (indicator gap is {_SELECTION_INDICATOR_GAP})"
    )


# Regression test for selected-row text visibility in directory tree and attachment list.
#
# This test verifies the bug introduced by commit fbb9fd4 where selected-row text
# became invisible in the directory tree and task attachment list (preview_list).


_SELECTED_INACTIVE = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Selected
_UNSELECTED = QStyle.StateFlag.State_Enabled

# WCAG AA minimum contrast for body text
_MINIMUM_CONTRAST = 4.5


def _painted_colours(image):
    """Counts the colours of a row from its pixels, the most painted first."""
    counts = {}
    for y in range(image.height()):
        for x in range(image.width()):
            key = image.pixelColor(x, y).rgb()
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda pair: -pair[1])


def _ink_contrast(view, item, state):
    """The ink colour of a row, the background colour and their contrast.

    The ink is the pixel that stands furthest from the background among the
    columns the cells are painted in, leaving the rail at the left edge out.
    The cells are drawn in a single colour, but a platform that smooths its
    glyphs blends them with the background, so the furthest shade still
    carries the text where the most painted colours would name the rail.
    """
    palette = view.viewport().palette()
    image = render_row(view, item, state, palette)
    painted = _painted_colours(image)
    background = QColor(painted[0][0])
    ink = max(
        (
            image.pixelColor(x, y)
            for x in range(_SELECTION_INDICATOR_WIDTH, image.width())
            for y in range(image.height())
        ),
        key=lambda colour: _contrast_ratio(colour, background),
    )
    return ink, background, _contrast_ratio(ink, background)


def _wcag_contrast_ratio(first: QColor, second: QColor) -> float:
    """Returns the contrast ratio between two colours, as WCAG defines it."""

    def _relative_luminance(colour: QColor) -> float:
        def channel(value: float) -> float:
            if value <= 0.03928:
                return value / 12.92
            return ((value + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(colour.redF())
            + 0.7152 * channel(colour.greenF())
            + 0.0722 * channel(colour.blueF())
        )

    lighter = max(_relative_luminance(first), _relative_luminance(second))
    darker = min(_relative_luminance(first), _relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def _readable_ink(view, item, state):
    """Asserts the ink of a row reads against its background, smoothed or not."""
    ink, background, ratio = _ink_contrast(view, item, state)
    assert ratio >= _MINIMUM_CONTRAST, f"{ink.name()} on {background.name()}: {ratio}"


# Test with available styles


def _restore_style(qapp, name):
    style = QStyleFactory.create(name)
    if style is not None:
        qapp.setStyle(style)


@pytest.fixture(params=_STYLES)
def styled_for_regression(request, qapp):
    """Sets a style on the application for one test and puts the old one back."""
    original = qapp.style().objectName()
    style = QStyleFactory.create(request.param)
    if style is None:
        pytest.skip(f"{request.param} cannot be created")
    qapp.setStyle(style)
    yield request.param
    _restore_style(qapp, original)


class _NoSelectionStyle(QProxyStyle):
    """A style that paints no selection of its own."""

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            return
        super().drawControl(element, option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_PanelItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            return
        super().drawPrimitive(element, option, painter, widget)


@pytest.fixture
def no_selection_style(qapp):
    """Puts a style that paints no selection on the application."""
    style_name = qapp.style().objectName()
    qapp.setStyle(_NoSelectionStyle(QStyleFactory.create(style_name)))
    yield
    _restore_style(qapp, style_name)


def test_a_selected_directory_tree_row_renders_readable_text(
    styled_for_regression, window, tmp_path
):
    """Selected row in directory tree must have readable text.

    This is a regression test for commit fbb9fd4 which unified selection
    appearance but caused selected-row text to become invisible in the
    directory tree and preview_list.
    """
    (tmp_path / "Reports").mkdir()
    (tmp_path / "Projects").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        _readable_ink(tree, item, state)


def test_a_selected_preview_list_row_renders_readable_text(
    styled_for_regression, window, tmp_path, make_task
):
    """Selected row in preview list (attachment list) must have readable text.

    This is a regression test for commit fbb9fd4 which unified selection
    appearance but caused selected-row text to become invisible in the
    directory tree and preview_list.
    """
    file = make_task(tmp_path, "260918", "Task With Attachments")
    # Add an attachment to the task folder
    attachment = file.parent / "note.txt"
    attachment.write_text("attachment content")

    window.navigate_to(tmp_path)
    listing = window.tabs.widget(0).listing
    task_item = listing.item(0)
    listing.setCurrentItem(task_item)

    # The preview_list is populated when a task is selected
    import time
    time.sleep(0.1)

    preview_list = window.preview_area.preview_list
    if preview_list.count() > 0:
        item = preview_list.item(0)
        for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
            _readable_ink(preview_list, item, state)


def test_a_selected_row_is_tinted_in_directory_tree(
    no_selection_style, window, tmp_path
):
    """Selected row in directory tree shows the selection tint even when style paints none."""
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")
    palette = tree.viewport().palette()

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        tint = _selection_tint(_row_option(tree, item, state))
        assert row_background(render_row(tree, item, state, palette)) == tint


def test_a_selected_row_is_tinted_in_preview_list(
    no_selection_style, window, tmp_path, make_task
):
    """Selected row in preview list shows the selection tint even when style paints none."""
    file = make_task(tmp_path, "260918", "Task With Attachments")
    attachment = file.parent / "note.txt"
    attachment.write_text("attachment content")

    window.navigate_to(tmp_path)
    listing = window.tabs.widget(0).listing
    task_item = listing.item(0)
    listing.setCurrentItem(task_item)

    import time
    time.sleep(0.1)

    preview_list = window.preview_area.preview_list
    if preview_list.count() > 0:
        item = preview_list.item(0)
        palette = preview_list.viewport().palette()

        for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
            tint = _selection_tint(_row_option(preview_list, item, state))
            assert row_background(render_row(preview_list, item, state, palette)) == tint


def _row_option(view, item, state):
    """The option a row is rendered from, built the way `render_row` builds it."""
    rect = QRect(view.visualItemRect(item))
    index = view.indexFromItem(item)
    option = QStyleOptionViewItem()
    view.itemDelegate().initStyleOption(option, index)
    option.rect = QRect(0, 0, rect.width(), rect.height())
    option.state = state
    option.palette = view.viewport().palette()
    option.widget = view
    return option
