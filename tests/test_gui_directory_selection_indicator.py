"""Regression tests for the selection indicator of the directory tree.

`QTreeView` paints the part of a selected row that lies before its items
itself, through `PE_PanelItemViewRow`, before the item delegate sees the row.
Clearing `State_Selected` inside the delegate cannot remove that native fill:
it stayed behind the custom `[` outline, and the outline sat at the item's text
origin rather than where the native bar was, at the left edge of the row.
"""

from collections import Counter

import pytest
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QStyleFactory

from mktsk.gui.tasklist import (
    _ROW_LINE_REACH,
    _SELECTION_INDICATOR_GAP,
    _SELECTION_INDICATOR_WIDTH,
    _contrast_ratio,
)
from tests.gui_helpers import find_directory

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
