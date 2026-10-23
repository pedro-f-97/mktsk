"""Tests for the unified selection delegate with empty text."""

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyleOptionViewItem

from mktsk.gui.tasklist import _UnifiedSelectionDelegate


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
