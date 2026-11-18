"""The selection look shared by the task list, the attachment list and the tree."""


from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPalette,
)
from PySide6.QtWidgets import (
    QProxyStyle,
    QStyle,
    QStyledItemDelegate,
    QStyleOption,
    QStyleOptionViewItem,
    QWidget,
)

# the selection is painted by the delegates rather than the style, so it looks
# the same on every platform: a faint tint and a rounded Highlight rail on the
# left. The gap is the rail plus a margin, which keeps content clear of it
_SELECTION_INDICATOR_WIDTH = 4
_SELECTION_INDICATOR_RADIUS = 2.0
_SELECTION_INDICATOR_GAP = _SELECTION_INDICATOR_WIDTH + 2

# how far the top and bottom bracket lines reach past the rail
_ROW_LINE_REACH = 8

# how far the selection tint blends from Base towards Highlight
_SELECTION_TINT_WEIGHT = 0.25


def _relative_luminance(colour: QColor) -> float:
    """Returns the relative luminance of a colour, as WCAG defines it.

    Args:
        colour: the colour to measure.

    Returns:
        The luminance, from 0 for black to 1 for white.
    """

    def channel(value: float) -> float:
        if value <= 0.03928:
            return value / 12.92

        return ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(colour.redF())
        + 0.7152 * channel(colour.greenF())
        + 0.0722 * channel(colour.blueF())
    )


def _contrast_ratio(first: QColor, second: QColor) -> float:
    """Returns the contrast ratio between two colours, as WCAG defines it.

    Args:
        first: one of the two colours.
        second: the other one.

    Returns:
        The ratio, from 1 for two equal colours upwards.
    """
    lighter = max(_relative_luminance(first), _relative_luminance(second))
    darker = min(_relative_luminance(first), _relative_luminance(second))

    return (lighter + 0.05) / (darker + 0.05)


def _blend(base: QColor, text: QColor, weight: float) -> QColor:
    """Blends two colours, from `base` at weight 0 to `text` at weight 1.

    Args:
        base: the colour the blend starts from.
        text: the colour the blend runs towards.
        weight: how far to move, from 0 to 1.

    Returns:
        The blended colour.
    """
    channels = (
        round(base.red() + (text.red() - base.red()) * weight),
        round(base.green() + (text.green() - base.green()) * weight),
        round(base.blue() + (text.blue() - base.blue()) * weight),
    )
    return QColor(*(max(0, min(255, value)) for value in channels))


def _colour_group(state: QStyle.StateFlag) -> QPalette.ColorGroup:
    """Returns the palette group the style paints a row of this state from.

    Args:
        state: the state of the row being painted.

    Returns:
        The active, inactive or disabled group of the palette.
    """
    if not (state & QStyle.StateFlag.State_Enabled):
        return QPalette.ColorGroup.Disabled

    if state & QStyle.StateFlag.State_Active:
        return QPalette.ColorGroup.Active

    return QPalette.ColorGroup.Inactive


def _selection_tint(option: QStyleOption) -> QColor:
    """Returns the selection fill: `Base` blended a little towards `Highlight`.

    Read from the palette, so it follows light and dark themes.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The faint selection tint of the palette group of the state.
    """
    group = _colour_group(option.state)
    palette = option.palette
    return _blend(
        palette.color(group, QPalette.ColorRole.Base),
        palette.color(group, QPalette.ColorRole.Highlight),
        _SELECTION_TINT_WEIGHT,
    )


def _paint_selection(painter: QPainter, option: QStyleOptionViewItem) -> None:
    """Paints the selection tint and the rail over the style's own selection.

    Args:
        painter: the painter the row is being drawn with.
        option: what the row is painted from, holding its rect and its state.
    """
    group = _colour_group(option.state)
    painter.fillRect(option.rect, _selection_tint(option))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(option.palette.color(group, QPalette.ColorRole.Highlight))
    painter.drawRoundedRect(
        QRectF(
            option.rect.left(),
            option.rect.top(),
            _SELECTION_INDICATOR_WIDTH,
            option.rect.height(),
        ),
        _SELECTION_INDICATOR_RADIUS,
        _SELECTION_INDICATOR_RADIUS,
    )
    painter.restore()


def _paint_selection_lines(
    painter: QPainter, option: QStyleOptionViewItem, left: int | None = None
) -> None:
    """Paints the rail and the bracket lines of a selected row.

    Args:
        painter: the painter the row is being drawn with.
        option: what the row is painted from, holding its rect, state and palette.
        left: the column the rail starts at, or None for the left edge of the
            row's item, which is where a list without indentation starts.
    """
    group = _colour_group(option.state)
    rect = option.rect
    left = rect.left() if left is None else left
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(option.palette.color(group, QPalette.ColorRole.Highlight))
    painter.drawRoundedRect(
        QRectF(
            left,
            rect.top(),
            _SELECTION_INDICATOR_WIDTH,
            rect.height(),
        ),
        _SELECTION_INDICATOR_RADIUS,
        _SELECTION_INDICATOR_RADIUS,
    )
    painter.restore()
    # Bracket lines: top and bottom, from the rail to rail width + reach
    thickness = _SELECTION_INDICATOR_WIDTH
    reach = thickness + _ROW_LINE_REACH
    colour = option.palette.color(group, QPalette.ColorRole.Highlight)
    for top in (rect.top(), rect.bottom() + 1 - thickness):
        painter.fillRect(QRect(left, top, reach, thickness), colour)


class _DirectorySelectionStyle(QProxyStyle):
    """Paints the tree's selected row band with the selection tint.

    `QTreeView` paints that band before the item, out of the delegate's reach.
    """

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        if element == QStyle.PrimitiveElement.PE_PanelItemViewRow and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            painter.fillRect(option.rect, _selection_tint(option))
            return

        super().drawPrimitive(element, option, painter, widget)


class _UnifiedSelectionDelegate(QStyledItemDelegate):
    """Paints the shared selection look in the attachment list and the tree.

    Args:
        parent: the object that owns the delegate.
        rail_at_left_edge: whether the rail sits at the left edge of the view
            rather than at the left edge of the item. The directory tree
            indents its items, and the rail takes the place its native row
            panel used to fill, so it is asked for there.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        rail_at_left_edge: bool = False,
    ) -> None:
        super().__init__(parent)
        self.rail_at_left_edge = rail_at_left_edge

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        # the text of a selected row is painted after the tint, not by the style
        text = ""
        if selected:
            text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            option.text = ""

        # hide the selection from the style, which would paint its own indicator
        state = option.state
        if selected:
            option.state &= ~QStyle.StateFlag.State_Selected

        # Let the style paint the base (alternating rows, etc.) without selection
        super().paint(painter, option, index)

        # Restore selection state for our custom painting
        if selected:
            option.state = state
            # Fill the selection tint over the whole row
            painter.fillRect(option.rect, _selection_tint(option))
            # Draw rail and bracket lines
            left = 0 if self.rail_at_left_edge else option.rect.left()
            _paint_selection_lines(painter, option, left)

            # Paint the text on top of the selection
            if text:
                painter.save()
                pen_colour = _cell_pen(option)
                painter.setPen(pen_colour)
                # Use the same alignment as the style would: left + vcenter
                text_rect = option.rect.adjusted(
                    _SELECTION_INDICATOR_GAP, 0, 0, 0
                )
                painter.drawText(
                    text_rect,
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    text,
                )
                painter.restore()


def _cell_pen(option: QStyleOptionViewItem) -> QColor:
    """Returns the text colour of a cell.

    On a selected row, `HighlightedText` or `Text`, whichever contrasts better
    with the tint.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour the row is drawn in.
    """
    group = _colour_group(option.state)
    palette = option.palette

    if not (option.state & QStyle.StateFlag.State_Selected):
        return palette.color(group, QPalette.ColorRole.Text)

    background = _selection_tint(option)
    highlighted = palette.color(group, QPalette.ColorRole.HighlightedText)
    plain = palette.color(group, QPalette.ColorRole.Text)
    return (
        plain
        if _contrast_ratio(plain, background) > _contrast_ratio(highlighted, background)
        else highlighted
    )
