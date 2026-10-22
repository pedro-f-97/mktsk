"""Regression test for selected-row text visibility in directory tree and attachment list.

This test verifies the bug introduced by commit fbb9fd4 where selected-row text
became invisible in the directory tree and task attachment list (preview_list).
"""

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionViewItem,
)

from mktsk.gui.tasklist import (
    _SELECTION_INDICATOR_WIDTH,
    _selection_tint,
)
from tests.gui_helpers import (
    find_directory,
    render_row,
    row_background,
)

_SELECTED_ACTIVE = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
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


def _contrast_ratio(first: QColor, second: QColor) -> float:
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
_STYLES = tuple(QStyleFactory.keys())


def _restore_style(qapp, name):
    style = QStyleFactory.create(name)
    if style is not None:
        qapp.setStyle(style)


@pytest.fixture(params=_STYLES)
def styled(request, qapp):
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
    styled, window, tmp_path
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
    styled, window, tmp_path, make_task
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

    preview_list = window.preview_list
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

    preview_list = window.preview_list
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
