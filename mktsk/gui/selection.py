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

# the selection of a task row is the delegate's own, because the platform
# styles paint one in a shape of their own: a faint tint of the palette
# covers the whole selected area, the task row and the band it opens, so the
# two read as one, and a rail of the full Highlight sits at its left edge,
# wide enough to read and rounded at both ends. The gap is the rail plus a
# small margin, which indents the action bar of the auxiliary row, so the
# rail stays visible at the left edge of the row and the bar never covers it
_SELECTION_INDICATOR_WIDTH = 4
_SELECTION_INDICATOR_RADIUS = 2.0
_SELECTION_INDICATOR_GAP = _SELECTION_INDICATOR_WIDTH + 2

# how far the top and bottom lines of a selected row reach past the rail, in
# logical pixels like the rail's own metrics: the rail's thickness plus this
# is the whole arm of a line, a short bracket that stays inside the first
# cell, so tuning how far the lines reach is one edit
_ROW_LINE_REACH = 8

# how far the tint of a selection moves from the Base towards the Highlight,
# subtle enough to keep the row close to the plain background it sits on
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
    """Blends two colours by a weight, from the base towards the text one.

    Both colours come from the same palette group, so a stripe stays a shade of
    the background it is drawn on rather than a colour written down. A weight
    of 0 gives the base, 1 gives the text, and anything between the colour that
    far along; no channel leaves the 0-255 range.

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
    """Returns the palette group the style paints a row of a state from.

    The style picks the group from the state itself, so the text has to pick
    the same one or it would read a colour from a group the background was not
    painted with.

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
    """Returns the colour the delegate fills a selected row with.

    The tint is the `Base` of the palette group the state belongs to, blended
    a little towards its `Highlight`, so a selected area reads apart from the
    rows around it with no colour written down: a light or dark mode and a
    new accent are followed through the palette alone. It is what both lines
    of a selected row are made of, the task row and the band it opens, and it
    is also what the text is measured against, so the pen stays paired with
    the background it is drawn on.

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
    """Paints the selection of a task row over the one the style painted.

    The style paints its own selection first and this covers it, so the look
    is the delegate's and stays the same under every style: a faint tint
    across the whole selected area, task row and band alike, and a rail of
    the full `Highlight` at its left edge, wide enough to read and rounded at
    both ends. Both colours come from the palette of the group the state
    belongs to, so the selection follows the theme without a colour written
    down here.

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
    """Paints the rail and bracket lines for a selected row.

    This is the `[` outline treatment shared by all three lists: a rounded rail
    of the full Highlight at the left edge, and short lines along the top and
    bottom edges reaching past the rail.

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
    """Leaves the selection of a directory row to the delegate.

    `QTreeView` paints the part of a selected row that lies before its items
    itself, through `PE_PanelItemViewRow`, before the item delegate sees the
    row. Clearing `State_Selected` in the delegate therefore never removed that
    native fill. The tree paints the band with the tint the delegate uses
    instead, so the custom rail at the left edge is the only indicator.
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
    """A delegate that paints the unified selection appearance.

    Used by the attachment list and directory tree to match the task list's
    selection: a tinted background (Base blended toward Highlight), a rounded
    rail of full Highlight at the left edge, and bracket lines at the top and
    bottom.

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

        # For selected rows, we need to paint text on top of the selection tint.
        # Clear option.text so the style doesn't paint it, then we'll paint it
        # ourselves after the selection background.
        text = ""
        if selected:
            text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            option.text = ""

        # Suppress the native selection indicator by clearing State_Selected
        # before the base class paints. The base class would otherwise paint
        # its own indicator (a vertical bar) which we replace with our custom
        # '[' outline (rounded rail + bracket lines).
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
    """Returns the colour of the text of a cell, paired with its background.

    An unselected row keeps the Text of the group its state belongs to. A
    selected one is drawn on the tint the delegate fills it with, so the text
    is the HighlightedText or the Text of that group, whichever holds better
    against that tint: both come from the palette and the better contrast
    wins, so no colour is written down here.

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
