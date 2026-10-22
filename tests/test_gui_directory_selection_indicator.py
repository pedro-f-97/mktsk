"""Regression test for duplicate selection indicators in directory tree.

The directory tree uses _UnifiedSelectionDelegate which paints a custom '['
outline (rounded rail + bracket lines). However, the base QStyledItemDelegate
also paints the native Qt selection indicator (a vertical bar at the left edge),
resulting in two indicators being visible.
"""

from collections import Counter

from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QStyle

from mktsk.gui.tasklist import (
    _SELECTION_INDICATOR_GAP,
    _SELECTION_INDICATOR_WIDTH,
    _contrast_ratio,
)
from tests.gui_helpers import find_directory, render_row

_SELECTED_ACTIVE = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
_SELECTED_INACTIVE = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Selected


def _count_vertical_indicators(image: QImage, highlight: QColor) -> int:
    """Count distinct vertical indicator lines at the left edge of a selected row.

    The custom indicator is a rounded rail of width _SELECTION_INDICATOR_WIDTH
    at x=0. The native indicator would be a separate vertical line, typically
    at x=0 or x=1. We scan the leftmost columns for the highlight colour and
    count contiguous vertical runs that span most of the row height.
    """
    height = image.height()
    if height == 0:
        return 0

    # Scan the first few columns for vertical lines of the highlight colour
    # A real indicator spans most of the row height
    min_span = height * 0.6  # at least 60% of row height
    indicator_columns = []

    for x in range(min(6, image.width())):  # Check first 6 columns
        highlight_pixels = 0
        for y in range(height):
            if image.pixelColor(x, y) == highlight:
                highlight_pixels += 1
        if highlight_pixels >= min_span:
            indicator_columns.append(x)

    # Group contiguous columns into single indicators
    if not indicator_columns:
        return 0

    groups = 1
    for i in range(1, len(indicator_columns)):
        if indicator_columns[i] > indicator_columns[i - 1] + 1:
            groups += 1
    return groups


def test_directory_tree_selected_row_has_single_indicator(window, tmp_path):
    """Selected row in directory tree must have exactly one selection indicator.

    The custom '[` outline (rounded rail + brackets) should be the only
    indicator. The native Qt vertical bar must be suppressed.
    """
    (tmp_path / "Reports").mkdir()
    (tmp_path / "Projects").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    palette = tree.viewport().palette()
    highlight = palette.color(QPalette.ColorRole.Highlight)

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        image = render_row(tree, item, state, palette)
        indicator_count = _count_vertical_indicators(image, highlight)
        assert indicator_count == 1, (
            f"Expected 1 selection indicator, found {indicator_count}. "
            f"This indicates both native and custom indicators are visible."
        )


def test_directory_tree_indicator_position(window, tmp_path):
    """The custom indicator rail should be at the left edge (x=0)."""
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    palette = tree.viewport().palette()
    highlight = palette.color(QPalette.ColorRole.Highlight)

    image = render_row(tree, item, _SELECTED_ACTIVE, palette)

    # The rail should occupy columns 0 to _SELECTION_INDICATOR_WIDTH - 1
    rail_columns = []
    for x in range(_SELECTION_INDICATOR_WIDTH):
        for y in range(image.height()):
            if image.pixelColor(x, y) == highlight:
                rail_columns.append(x)
                break

    assert rail_columns == list(range(_SELECTION_INDICATOR_WIDTH)), (
        f"Rail should occupy columns 0-{_SELECTION_INDICATOR_WIDTH - 1}, "
        f"found {rail_columns}"
    )


def test_directory_tree_text_spacing(window, tmp_path):
    """Text should start after the indicator gap, leaving adequate space."""
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    palette = tree.viewport().palette()
    palette.color(QPalette.ColorRole.Base)
    image = render_row(tree, item, _SELECTED_ACTIVE, palette)

    # Find the leftmost text pixel (high contrast against background)
    # Actually the selected row has a tint, so find the dominant colour
    counts = Counter(
        image.pixelColor(x, y).rgb()
        for y in range(image.height())
        for x in range(image.width())
    )
    bg_colour = QColor(counts.most_common(1)[0][0])

    _MINIMUM_CONTRAST = 4.5
    first_text_x = None
    for x in range(image.width()):
        for y in range(image.height()):
            colour = image.pixelColor(x, y)
            if _contrast_ratio(colour, bg_colour) >= _MINIMUM_CONTRAST:
                first_text_x = x
                break
        if first_text_x is not None:
            break

    assert first_text_x is not None, "No text found on selected row"
    # Text should start at or after the indicator gap
    assert first_text_x >= _SELECTION_INDICATOR_GAP, (
        f"Text starts at x={first_text_x}, expected at least "
        f"_SELECTION_INDICATOR_GAP={_SELECTION_INDICATOR_GAP}"
    )
