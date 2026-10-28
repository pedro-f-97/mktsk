"""The tasks of a category as a list, with the actions on the selected row."""

import datetime
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import (
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QProxyStyle,
    QStyle,
    QStyledItemDelegate,
    QStyleOption,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mktsk import helpers, listing, parsing, standards

from .icons import (
    _ICON_SIZE,
    _draw_bell,
    _draw_bell_plus,
    _draw_clip,
    _draw_close,
    _draw_folder,
    _draw_pencil,
    _draw_plus,
    _draw_reopen,
    _draw_state,
    _icon_button,
    _icon_pen,
    _stroked_icon,
)
from .reminders_scheduler import ReminderScheduler
from .reminders_ui import AddReminderDialog, RemindersDialog

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_AGE_ROLE = Qt.ItemDataRole.UserRole + 3
_STATE_ROLE = Qt.ItemDataRole.UserRole + 4
# the category a heading stands for, carried by the `All` headings alone: an
# archive heading lists no folder that a new task could land in, so it has none
_CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 5

# the mime type a drag of a task carries: the folder of the task, so a drop
# knows which task it moves without reading anything, and a drag from
# elsewhere is never taken for one of ours
_MIME_TYPE = "application/x-mktsk-task"

_ACTION_BAR_PADDING = 4

# the columns of a task row, from the left: the date of the folder, the task
# itself, a paperclip and the number of attachments it carries when it has any,
# the state it is in, how many interventions it carries, and how long ago the
# last was. The clip heading carries no name, because the paperclip says it
_HEADINGS = ("Date", "Task", "", "State", "Interventions", "Last activity")

# the states the change-state action offers: `closed` only comes from closing
# the task, which is a different operation
_OFFERED_STATES = tuple(state for state in parsing.STATES if state != "closed")

_COLUMN_PADDING = 6

# how far a stripe and a separator are blended from the base towards the text
# colour: both subtle, the separator a touch stronger, so a category reads
# apart from the rows under it without a colour written down
_ZEBRA_WEIGHT = 0.03
_SEPARATOR_WEIGHT = 0.08

# how far the tint of a drop target moves from the Base towards the Highlight:
# clear enough to say the category would take the task, and as far from the
# other tints as a category heading is from a task row
_DROP_TINT_WEIGHT = 0.35

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
_DATE_TEXT_LEFT_PADDING = _SELECTION_INDICATOR_GAP  # at least _INDICATOR_WIDTH + 2

# how far the top and bottom lines of a selected row reach past the rail, in
# logical pixels like the rail's own metrics: the rail's thickness plus this
# is the whole arm of a line, a short bracket that stays inside the first
# cell, so tuning how far the lines reach is one edit
_ROW_LINE_REACH = 8

# how far the tint of a selection moves from the Base towards the Highlight,
# subtle enough to keep the row close to the plain background it sits on
_SELECTION_TINT_WEIGHT = 0.25

# the marker a heading carries when it stands for the destination: a small dot
# at the right end of the row, clear of the name the style draws from the left
_MARKER_RADIUS = 4.0
_MARKER_INSET = 12

# how the text of a cell sits in the column of it: read from the left and
# centred, so a row of one line looks like the headings above it
_CELL_ALIGNMENT = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
_COUNT_ALIGNMENT = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

# maximum width of the task column in logical pixels
_TASK_MAX_WIDTH = 480


class _Columns(NamedTuple):
    """The widths of the fixed columns of a row, but the task one."""

    date: int
    clip: int
    state: int
    interventions: int
    activity: int


def _column_widths() -> _Columns:
    """Measures the fixed columns as wide as their contents.

    A heading is the widest thing its column holds, so measuring one keeps the
    column as narrow as it can be and never clipping it. The clip column has no
    heading, so it is measured from the paperclip and the two digits it may hold
    at once, taken from the icon size and the font in use rather than from
    numbers of their own. The date column is measured from the date itself, like
    any other column, and is narrowed to just that: the room the action bar
    needs is taken only by the selected row, which shifts as a whole, so no
    column has to carry it. The widths come from the font in use rather than
    from numbers written down, so a font of another size needs no constant of
    its own. They are the initial sizes the header starts its sections from;
    after that the header owns its geometry and the cells read it back.

    Returns:
        The width of the date column, of the clip one, of the state one, of the
        interventions one and of the last activity one.
    """
    heading_font = QFont(QApplication.font())
    heading_font.setBold(True)
    headings = QFontMetrics(heading_font)
    body = QFontMetrics(QApplication.font())

    return _Columns(
        body.horizontalAdvance("dd/mm/yyyy") + 2 * _COLUMN_PADDING,
        _ICON_SIZE + body.horizontalAdvance("44") + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[3]) + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[4]) + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[5]) + 2 * _COLUMN_PADDING,
    )


def _relative_age(last_activity: datetime.date, today: datetime.date) -> str:
    """Says how long ago a task was last worked on.

    The age reads the way a person says it, rather than as a date: today,
    yesterday, or the number of days back to it. A date that has not come yet
    reads as today, because a folder named with it is still a task.

    Args:
        last_activity: the most recent intervention of the task.
        today: the day the age is counted against.

    Returns:
        The age of the last activity of the task.
    """
    days = (today - last_activity).days

    if days <= 0:
        return "today"

    if days == 1:
        return "yesterday"

    return f"{days} days ago"


def _name_of(entry: listing.TaskEntry) -> str:
    """Returns the name that carries the date of a task.

    The date a task was created on is the one its folder carries, or the one
    its archive carries when the task is closed.

    Args:
        entry: the task folder or archive.

    Returns:
        The task folder name, or the archive name without its suffix.
    """
    name = entry.file.name
    if standards.is_task_archive(name):
        return name.removesuffix(standards._ARCHIVE_SUFFIX)

    return entry.file.parent.name


def _date_cell(entry: listing.TaskEntry) -> str:
    """Says the date of a task, as the Date column shows it.

    The date a task was created on is the one its folder carries, or the one
    its archive carries when the task is closed. It is read back with the same
    parser that recognises a task name, so a name that turns out not to be one
    gives its raw prefix rather than nothing.

    Args:
        entry: the task folder or archive.

    Returns:
        The date of the task as `dd/mm/yyyy`, or the raw prefix of its name.
    """
    name = _name_of(entry)
    parts = standards._task_date_and_title(name)
    if parts is None:
        return name.partition(standards._TASK_NAME_SEPARATOR)[0]

    return parts[0].strftime(helpers.DATE_FORMAT)


def _order_key(item: QListWidgetItem, column: int) -> datetime.date | str | int:
    """Returns the value a task row is ordered by, in a column.

    The date is the one the folder name carries, so a name that is not a task
    folder sorts last. The task compares without case, the state by the order
    of the domain, and the interventions as a number, so ten comes after nine.
    The clip column carries no order, so it is never asked for a key.

    Args:
        item: the row, carrying its task entry.
        column: the index of the column, from the date on the left.

    Returns:
        The value the row sorts by.
    """
    entry = item.data(_ENTRY_ROLE)

    if column == 0:
        parts = standards._task_date_and_title(_name_of(entry))
        return parts[0] if parts is not None else datetime.date.max

    if column == 1:
        return entry.title.casefold()

    if column == 3:
        return parsing.STATES.index(entry.state)

    if column == 4:
        return entry.interventions

    return entry.last_activity


class _ColumnHeader(QHeaderView):
    """The column headings, and the only source of column geometry.

    Each section is interactive, so a separator can be dragged to give a column
    more or less room, and the delegate reads every column back from here rather
    than measuring one of its own. The clip column is held at the width its
    paperclip and its two digits need and cannot be dragged, because it holds
    nothing a person would want to make room for. The date and the three right
    columns start from the widths of their contents, and the task takes the rest
    of the room a row has. No section is held wider than its contents: the
    action bar is taken by the auxiliary row the selected row opens below its
    own, so the date is a column like any other.
    """

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFixedHeight(height)
        model = QStandardItemModel(0, 6, self)
        for i, text in enumerate(_HEADINGS):
            item = QStandardItem(text)
            if i == 4:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            model.setHorizontalHeaderItem(i, item)
        self.setModel(model)
        self.setSectionsMovable(False)
        self.setSectionsClickable(True)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # the clip column is a fixed size, so it holds its paperclip and its
        # number whatever the rest of the row does
        self.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        cols = _column_widths()
        self.setMinimumSectionSize(min(cols))
        total = cols.clip + cols.state + cols.interventions + cols.activity
        # the task column starts as the rest of the room a row has; auto-width
        # grows it from here up to the cap and never below it
        self.default_task_width = max(total, 100)
        self.resizeSection(0, cols.date)
        self.resizeSection(1, self.default_task_width)
        self.resizeSection(2, cols.clip)
        self.resizeSection(3, cols.state)
        self.resizeSection(4, cols.interventions)
        self.resizeSection(5, cols.activity)


class _ActionBar(QWidget):
    """The actions offered for the selected task, aligned to the left.

    The buttons carry an icon and a tooltip rather than a label, which keeps the
    bar narrow enough to sit on a row without hiding much of it.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        # the listing positions the bar, so the layout must not resize it
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_ACTION_BAR_PADDING)

        self.open_button = _icon_button(
            self, "Open the task folder", _draw_folder, "OpenTask"
        )
        self.resume_button = _icon_button(
            self, "Add a note for today", _draw_plus, "ResumeTask"
        )
        self.rename_button = _icon_button(
            self, "Rename this task", _draw_pencil, "RenameTask"
        )
        self.state_button = _icon_button(
            self, "Change the state of this task", _draw_state, "ChangeState"
        )
        self.close_button = _icon_button(self, "Close this task", _draw_close, "CloseTask")
        # the reminder buttons speak to the reminders of the task rather than
        # to the task itself, and stand only when the window carries a
        # scheduler behind them, so a run without a tray never offers them
        self.add_reminder_button = _icon_button(
            self, "Add reminder", _draw_bell_plus, "AddReminder"
        )
        self.reminders_button = _icon_button(
            self, "Reminders", _draw_bell, "Reminders"
        )
        self._reminders_available = False
        self._reopening = False
        # the resume button is the one set_reopening turns into the reopen
        # action, so what it starts with is what puts back
        self._resume_icon = self.resume_button.icon()
        self._resume_tooltip = self.resume_button.toolTip()
        self.state_menu = QMenu(self.state_button)
        for offered in _OFFERED_STATES:
            self.state_menu.addAction(offered)
        self.state_button.setMenu(self.state_menu)
        # the menu opens from the click rather than from the press, so the
        # button never waits for a menu that the click itself has to close
        self.state_button.clicked.connect(self._open_state_menu)
        # the archive button closes the task, so it stands last of the bar,
        # after even the reminder buttons when they are shown; the other
        # buttons keep their order
        for button in self.buttons()[:-1]:
            layout.addWidget(button)
        for button in self.reminder_buttons():
            layout.addWidget(button)
        layout.addWidget(self.close_button)
        self._update_reminder_buttons()
        # the stretch keeps the surplus of the bar away from the buttons, so
        # they pack to the left edge even when only the reopen one is shown
        layout.addStretch()

    def _open_state_menu(self) -> None:
        """Opens the menu of states under the button that carries it."""
        self.state_menu.popup(
            self.state_button.mapToGlobal(self.state_button.rect().bottomLeft())
        )

    def buttons(self) -> tuple[QToolButton, ...]:
        """Returns the five action buttons, in order."""
        return (
            self.open_button,
            self.resume_button,
            self.rename_button,
            self.state_button,
            self.close_button,
        )

    def reminder_buttons(self) -> tuple[QToolButton, ...]:
        """Returns the two reminder buttons, in order."""
        return (self.add_reminder_button, self.reminders_button)

    def set_reminders_available(self, available: bool) -> None:
        """Offers the reminder buttons only when a scheduler stands behind them.

        Args:
            available: whether the window carries a reminder scheduler.
        """
        self._reminders_available = available
        self._update_reminder_buttons()

    def _update_reminder_buttons(self) -> None:
        """Shows the reminder buttons on an open task when a scheduler exists."""
        visible = self._reminders_available and not self._reopening
        for button in self.reminder_buttons():
            button.setVisible(visible)

    def set_reopening(self, reopening: bool) -> None:
        """Offers reopen alone for a row that holds a closed task.

        The other four actions all speak to a folder, and only reopening
        makes the folder stand again, so they are left out until then. The
        button that carries resume carries the reopen icon and tooltip while
        it stands for reopening, because reopening an archived task is not
        adding a note for today; putting it back restores both. The reminder
        buttons go with the rest, because a closed task has neither a folder
        to remind about nor a place in the open tabs.

        Args:
            reopening: True when the selected row holds a closed task.
        """
        self._reopening = reopening
        for button in (
            self.open_button,
            self.rename_button,
            self.state_button,
            self.close_button,
        ):
            button.setVisible(not reopening)
        self._update_reminder_buttons()

        if reopening:
            self.resume_button.setIcon(
                _stroked_icon(
                    self.resume_button.palette().color(
                        QPalette.ColorRole.ButtonText
                    ),
                    _draw_reopen,
                )
            )
            self.resume_button.setToolTip("Reopen this task")
        else:
            self.resume_button.setIcon(self._resume_icon)
            self.resume_button.setToolTip(self._resume_tooltip)


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


class _TaskDelegate(QStyledItemDelegate):
    """Paints a row as the columns of the header, above the band it opens.

    Every column comes from the header, which owns the geometry: the delegate
    asks it for the position and the size of each section, so a heading never
    sits over a value of another column and dragging a separator moves the cells
    with it. The date and the title come from the task entry, and so does the
    number of attachments the clip column shows, while the state, the count and
    the age reach the delegate in the item roles, which the window fills from
    the task, so painting reads no file and holds no date of its own. A row
    without them is a heading, painted across the whole item.

    Every cell starts at the left edge of the row, laid out from the header, so
    selecting a row moves none of its cells. The action bar lives in an
    auxiliary row the selected row opens below its own, and only that row grows
    by the height of the band, its cells keeping the room a plain row has. The
    selection of a row is the delegate's own, painted over the style's: a faint
    tint across the task row and the band alike, so the two read as one, a
    rounded rail of the Highlight at the left edge, and a short line along the
    top and bottom edges of the whole selected row, from its left edge a little
    past the rail, so the rail and the lines bracket the row. The bar is
    indented past that rail rather than the cells being pushed right. The date
    is drawn after the same margin the header draws its own text with, so a
    heading and its value line up. Every row keeps the height the bar needs,
    which stops the list from shifting as the selection moves.

    Args:
        min_height: the height a plain row has, which is also the room the
            cells keep on the selected row, above the band it opens.
        accordion_height: the height of the band the action bar takes below the
            cells of the selected row.
        header: the header the geometry of every column is read from.
    """

    def __init__(
        self, min_height: int, accordion_height: int, header: _ColumnHeader
    ) -> None:
        super().__init__()
        self.min_height = min_height
        self.accordion_height = accordion_height
        self.header = header
        self.inset_row = -1
        # the category a heading stands for when it is the destination, held as
        # the string the row carries, or None when no category is the target
        self.destination: str | None = None
        # the row of the heading that stands for the category a drop would move
        # a task into, or -1 while no category is marked
        self.drop_row = -1

    def column_rect(self, row: QRect, column: int) -> QRect:
        """Returns the rectangle of a column within a row.

        The position and the size come from the header, so the cells of the
        list and the headings over them can never disagree; the row supplies
        the vertical extent and the horizontal origin, which moves with the
        horizontal scrollbar.

        Args:
            row: the row the column belongs to.
            column: the index of the column, from the date on the left.

        Returns:
            The rectangle the column occupies in the row.
        """
        return QRect(
            row.left() + self.header.sectionPosition(column),
            row.top(),
            self.header.sectionSize(column),
            row.height(),
        )

    def content_rect(self, row: QRect, column: int) -> QRect:
        """Returns the rectangle a cell is painted in, cut back to the row.

        A cell is its column of the row, cut back to what the row still holds
        past its right edge, so nothing of a row is ever painted outside it; the
        left edge is kept whatever the cut, so a cell that falls entirely past
        the edge keeps the position its column gave it.

        Args:
            row: the row the column belongs to.
            column: the index of the column, from the date on the left.

        Returns:
            The rectangle the cell is painted in.
        """
        cell = self.column_rect(row, column)
        available = row.right() - cell.left() + 1
        if available < cell.width():
            cell.setWidth(max(available, 0))
        return cell

    def content_band(self, row: QRect) -> QRect:
        """Returns the part of a row that holds its cells.

        The selected row opens the accordion band below, and its cells keep the
        room a plain row has, so they stay where every other row paints them.
        """
        return QRect(row.left(), row.top(), row.width(), min(row.height(), self.min_height))

    def _paint_row_lines(
        self, painter: QPainter, option: QStyleOptionViewItem
    ) -> None:
        """Paints the short lines that bracket a selected row with its rail.

        Both lines start at the left edge of the row and reach an arm of the
        rail's thickness plus `_ROW_LINE_REACH`, so the arm stays inside the
        first cell and its length is tuned in one place. The top line starts
        at the rail's first pixel row and the bottom one ends at its last,
        whatever the row height or the band the action bar opens, so the rail
        and the two lines read as a bracket around the whole selected row.
        They are filled on integer rectangles in the colour and the thickness
        of the rail, with no antialiasing, and only a selected task row gets
        them.

        Args:
            painter: the painter the row is being drawn with.
            option: what the row is painted from, holding its rect, state
                and palette.
        """
        rect = option.rect
        thickness = _SELECTION_INDICATOR_WIDTH
        reach = thickness + _ROW_LINE_REACH
        group = _colour_group(option.state)
        colour = option.palette.color(group, QPalette.ColorRole.Highlight)
        for top in (rect.top(), rect.bottom() + 1 - thickness):
            painter.fillRect(QRect(rect.left(), top, reach, thickness), colour)

    def initStyleOption(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Fills the option the style paints a row from, without its text.

        The base class fills option.text from the display role every time it
        paints, so emptying it in paint is lost on the copy paint is handed;
        a task row has to lose its text here, where that copy is filled. The
        style then draws the row background and nothing else, and the cells are
        drawn by paint, each in its own column. A heading keeps its text, so the
        style still paints it across the row.

        Args:
            option: the option the style will paint the row from.
            index: the index of the row being painted.
        """
        super().initStyleOption(option, index)
        if index.data(_COUNT_ROLE) is not None:
            option.text = ""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        count = index.data(_COUNT_ROLE)
        if count is None:
            # a separator is never selected and carries no bar, so it is painted
            # as an enabled row: both the fill and the text then come from the
            # palette group a task row uses, rather than the disabled grey a
            # non-selectable item would otherwise be drawn in
            separator_option = QStyleOptionViewItem(option)
            separator_option.state |= QStyle.StateFlag.State_Enabled
            group = _colour_group(separator_option.state)
            # the view fills the option's palette from the row it is about to
            # paint, and a non-selectable row reads its text from the Disabled
            # group; the state alone does not carry the style past that, so the
            # palette is pointed at the enabled group the fill comes from
            separator_option.palette.setCurrentColorGroup(group)
            if index.row() == self.drop_row:
                # the category a drop would move a task into, marked for as
                # long as the drag is over it
                painter.fillRect(
                    option.rect,
                    _blend(
                        option.palette.color(group, QPalette.ColorRole.Base),
                        option.palette.color(group, QPalette.ColorRole.Highlight),
                        _DROP_TINT_WEIGHT,
                    ),
                )
            else:
                painter.fillRect(
                    option.rect,
                    _blend(
                        option.palette.color(group, QPalette.ColorRole.Base),
                        option.palette.color(group, QPalette.ColorRole.Text),
                        _SEPARATOR_WEIGHT,
                    ),
                )
            super().paint(painter, separator_option, index)
            if self.destination is not None and (
                index.data(_CATEGORY_ROLE) == self.destination
            ):
                # the marker of the destination: a small dot at the right end
                # of its heading, clear of the name the style draws from the
                # left, in the colour the header icons carry
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(
                    option.palette.color(QPalette.ColorRole.ButtonText)
                )
                painter.drawEllipse(
                    QPointF(
                        option.rect.right() - _MARKER_INSET,
                        option.rect.center().y(),
                    ),
                    _MARKER_RADIUS,
                    _MARKER_RADIUS,
                )
                painter.restore()
            return

        # the row background is the style's, as it is for any view. A stripe
        # fills the whole row before the style paints, so hover and the native
        # look still draw on top; a selected row gets no stripe of its own,
        # because the selection tint the delegate paints covers it. The stripes
        # restart at every separator, so the first task under one is always the
        # plain base colour: the parity is counted from the rows above, back to
        # the row that carries no count, and nothing is remembered between
        # paints, so sorting or refreshing cannot leave a stripe behind.
        if not (option.state & QStyle.StateFlag.State_Selected):
            above = 0
            for row in range(index.row() - 1, -1, -1):
                if index.model().index(row, 0).data(_COUNT_ROLE) is None:
                    break
                above += 1
            if above % 2 == 1:
                group = _colour_group(option.state)
                painter.fillRect(
                    option.rect,
                    _blend(
                        option.palette.color(group, QPalette.ColorRole.Base),
                        option.palette.color(group, QPalette.ColorRole.Text),
                        _ZEBRA_WEIGHT,
                    ),
                )

        selected = index.row() == self.inset_row
        cells = self.content_band(option.rect) if selected else option.rect
        # the style paints the row first, and over it the selection this
        # delegate owns: the tint across the whole area, task row and band
        # alike, the rounded rail of the Highlight at its left edge, and the
        # short bracket lines at the rail's two ends
        super().paint(painter, option, index)
        if option.state & QStyle.StateFlag.State_Selected:
            _paint_selection(painter, option)
            self._paint_row_lines(painter, option)

        padding = self.header.style().pixelMetric(
            QStyle.PixelMetric.PM_HeaderMargin
        )
        entry = index.data(_ENTRY_ROLE)

        painter.save()
        pen_colour = _cell_pen(option)
        painter.setPen(pen_colour)

        date_cell = self.content_rect(cells, 0)
        # give the first column's text a left padding so the selection indicator
        # stays clear of the first glyph for all rows
        date_cell.setLeft(date_cell.left() + max(padding, _DATE_TEXT_LEFT_PADDING))
        date_text = option.fontMetrics.elidedText(
            _date_cell(entry), Qt.TextElideMode.ElideRight, date_cell.width()
        )
        painter.drawText(
            date_cell,
            _CELL_ALIGNMENT,
            date_text,
        )

        task_cell = self.content_rect(cells, 1)
        task_text = option.fontMetrics.elidedText(
            helpers.readable_title(entry.title),
            Qt.TextElideMode.ElideRight,
            task_cell.width(),
        )
        painter.drawText(
            task_cell,
            _CELL_ALIGNMENT,
            task_text,
        )

        # the clip column is blank until the task carries an attachment, and
        # then it shows the paperclip and the number of them, the number read
        # from the entry the row already holds
        clip_cell = self.content_rect(cells, 2)
        attachments = entry.attachments
        if attachments:
            icon = QRect(
                clip_cell.left() + _COLUMN_PADDING,
                clip_cell.top() + (clip_cell.height() - _ICON_SIZE) // 2,
                _ICON_SIZE,
                _ICON_SIZE,
            )
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(icon.left(), icon.top())
            clip_pen = (
                pen_colour
                if selected
                else option.palette.color(QPalette.ColorRole.ButtonText)
            )
            painter.setPen(_icon_pen(clip_pen))
            _draw_clip(painter, QRectF(0, 0, _ICON_SIZE, _ICON_SIZE))
            painter.restore()
            clip_cell.setLeft(clip_cell.left() + _COLUMN_PADDING + _ICON_SIZE)
        clip_text = str(attachments) if attachments else ""
        painter.drawText(
            clip_cell,
            _CELL_ALIGNMENT,
            option.fontMetrics.elidedText(
                clip_text, Qt.TextElideMode.ElideRight, clip_cell.width()
            ),
        )

        state_cell = self.content_rect(cells, 3)
        state_text = option.fontMetrics.elidedText(
            index.data(_STATE_ROLE) or "",
            Qt.TextElideMode.ElideRight,
            state_cell.width(),
        )
        painter.drawText(
            state_cell,
            _CELL_ALIGNMENT,
            state_text,
        )
        count_cell = self.content_rect(cells, 4)
        count_text = option.fontMetrics.elidedText(
            index.data(_COUNT_ROLE) or "",
            Qt.TextElideMode.ElideRight,
            count_cell.width(),
        )
        painter.drawText(
            count_cell,
            _COUNT_ALIGNMENT,
            count_text,
        )
        age_cell = self.content_rect(cells, 5)
        age_text = option.fontMetrics.elidedText(
            index.data(_AGE_ROLE) or "",
            Qt.TextElideMode.ElideRight,
            age_cell.width(),
        )
        painter.drawText(
            age_cell,
            _CELL_ALIGNMENT,
            age_text,
        )
        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = super().sizeHint(option, index)
        size.setWidth(self.header.length())
        height = max(size.height(), self.min_height)
        if index.isValid() and index.row() == self.inset_row and index.data(_ENTRY_ROLE) is not None:
            height += self.accordion_height
        size.setHeight(height)
        return size


class TaskListing(QListWidget):
    """A list of tasks with an action bar below the selected row.

    The bar follows the selected row in its own auxiliary row, and shows only
    when a task is selected. Headings are not selectable, so they never get
    one, and a closed task gets a single button, the reopen action, which still
    reports resume: the other actions all speak to a folder. The listing only
    reports which action was asked for, leaving the task logic to the window.

    A task that stands as a folder can be dragged onto a category, which moves
    the folder into it. The listing carries the drag and the drop, and reports
    the folder and the category it was dropped on, leaving the move itself to
    the window. A heading is not dragged: it stands for a category, and a
    closed task is not either, because its archive is not a folder to move.
    """

    open_requested = Signal(object)
    resume_requested = Signal(object)
    rename_requested = Signal(object)
    state_requested = Signal(object, str)
    close_requested = Signal(object)
    order_changed = Signal(int, bool)
    destination_requested = Signal(str)
    move_requested = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_bar = _ActionBar(self.viewport())
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.header = _ColumnHeader(
            self.action_bar.minimumSizeHint().height()
        )
        self.accordion_height = self.action_bar.sizeHint().height()
        self.delegate = _TaskDelegate(
            self.action_bar.minimumSizeHint().height(),
            self.accordion_height,
            self.header,
        )
        self.sort_column: int | None = None
        self.sort_descending = False
        self._task_section_user_resized = False
        self._fitting_task_column = False
        # the category the tasks of this listing stand in, for a tab of a
        # category, which holds no heading to say it
        self._category: Path | None = None
        self.setItemDelegate(self.delegate)
        self.header.sectionResized.connect(self._columns_changed)
        self.header.sectionClicked.connect(self._click_section)
        self.horizontalScrollBar().valueChanged.connect(self.header.setOffset)
        # a task is dragged onto a category, and a category is where it is
        # dropped, so the listing takes in a drag and hands one on
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        self.action_bar.open_button.clicked.connect(
            lambda: self._request(self.open_requested)
        )
        self.action_bar.resume_button.clicked.connect(
            lambda: self._request(self.resume_requested)
        )
        self.action_bar.rename_button.clicked.connect(
            lambda: self._request(self.rename_requested)
        )
        self.action_bar.close_button.clicked.connect(
            lambda: self._request(self.close_requested)
        )
        self.action_bar.add_reminder_button.clicked.connect(self._add_reminder)
        self.action_bar.reminders_button.clicked.connect(self._show_reminders)
        for action in self.action_bar.state_menu.actions():
            name = action.text()
            action.triggered.connect(
                lambda checked=False, new_state=name: self._request_state(new_state)
            )
        # a row becomes selected through a click, the keyboard or a programmatic
        # selection, all of which fire itemSelectionChanged; focus alone moves
        # only the current item, which must never show the bar or its room
        self.itemSelectionChanged.connect(self._sync_action_bar)
        self.itemClicked.connect(self._click_separator)
        self.action_bar.hide()
        # escape drops the selection only while the table, or a button on its
        # row, holds the focus, so the field and the selector above keep theirs
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.escape_shortcut.activated.connect(self._deselect)

    def selected_entry(self) -> listing.TaskEntry | None:
        """Returns the task of the selected row, or None when none is."""
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        item = selected_items[0]
        return item.data(_ENTRY_ROLE) if item else None

    def select_task(self, path: Path) -> bool:
        """Selects the task row of a folder path and scrolls it into view.

        The row may sit in another tab of the same window, which is switched
        to before the row is selected, so the selection, the action bar and
        the preview all follow the task as they would after a click. Selecting
        a task never moves the destination a new task would land in: that only
        changes when a category is picked, and nothing here picks one.

        Args:
            path: the .md of the task, or the archive that holds it, which is
                what the entry of the row carries.

        Returns:
            True when a row held the path and was selected, False when no row
            of this listing or of another tab holds it, leaving the selection
            and the current tab unchanged.
        """
        item = self._item_for(path)
        if item is not None:
            self.setCurrentItem(item)
            # The selection triggers _sync_preview which may show the preview
            # panel and resize the table. Defer the scroll until the layout
            # has settled, looking the row up again by path in case a refresh
            # replaced the item.
            QTimer.singleShot(0, lambda: self._scroll_to_path(path))
            return True

        window = self.window()
        tabs = getattr(window, "tabs", None)
        select_tab = getattr(window, "_select_tab", None)
        if tabs is None or select_tab is None:
            # a listing standing on its own, as a test builds one, has no
            # window to switch tabs in, so only its own rows can be selected
            return False

        for index in range(tabs.count()):
            other = tabs.widget(index).listing
            if other is self:
                continue
            item = other._item_for(path)
            if item is None:
                continue
            # switch first, then select: the preview follows the selection of
            # the current tab, so it must already be the tab holding the row
            select_tab(tabs.tabText(index))
            other.setCurrentItem(item)
            QTimer.singleShot(0, lambda other=other, path=path: other._scroll_to_path(path))
            return True

        return False

    def _item_for(self, path: Path) -> QListWidgetItem | None:
        """Returns the task row carrying a folder path, or None when none does.

        A row that carries no entry, a heading say, is skipped, so only a task
        or an archive can be the row a path reaches.

        Args:
            path: the .md of the task, or the archive that holds it.

        Returns:
            The row whose entry carries the path, or None.
        """
        for index in range(self.count()):
            item = self.item(index)
            entry = item.data(_ENTRY_ROLE)
            if entry is not None and entry.file == path:
                return item
        return None

    def _scroll_to_path(self, path: Path) -> None:
        """Scrolls to the row carrying a path, if it still exists.

        The item is looked up by path at the time of the scroll, not captured
        from the caller, so a refresh that replaced the row does not cause a
        crash or scroll to the wrong row.

        Args:
            path: the .md of the task, or the archive that holds it.
        """
        item = self._item_for(path)
        if item is not None:
            self.scrollToItem(item)

    def set_destination(self, directory: Path | None) -> None:
        """Points the marker at the category a new task would land in.

        Args:
            directory: the selected category, or None with the base directory.
        """
        self.delegate.destination = str(directory) if directory is not None else None
        self.viewport().update()

    def set_category(self, category: Path | None) -> None:
        """Points the listing at the category its tasks stand in.

        A tab of a category holds no heading, so the folder its tasks live in
        is told to the listing here, and a drop on one of its rows moves a
        task into that category. The `All` tab holds a heading per category
        and needs none of this.

        Args:
            category: the folder the tasks of this listing live in, or None
                when the listing stands for no category of its own.
        """
        self._category = category

    def _dragged_entry(self) -> listing.TaskEntry | None:
        """Returns the task a drag would carry, or None when there is none.

        A heading carries no task, and a closed task stands as an archive,
        which is not a folder to move, so neither of them is dragged.

        Returns:
            The task of the row the drag starts from, or None.
        """
        item = self.currentItem()
        if item is None:
            return None

        entry = item.data(_ENTRY_ROLE)
        if entry is None or standards.is_task_archive(entry.file.name):
            return None

        return entry

    def _drag_mime(self, entry: listing.TaskEntry) -> QMimeData:
        """Builds the payload a drag of a task carries.

        The payload holds the folder of the task, so a drop knows which task
        it moves without reading anything.

        Args:
            entry: the task being dragged.

        Returns:
            The payload of the drag.
        """
        mime = QMimeData()
        mime.setData(_MIME_TYPE, str(entry.file.parent).encode())
        return mime

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Starts a drag carrying the folder of the task under the cursor.

        Args:
            supportedActions: the actions the view supports, unused: the drag
                is a move, and only a move.
        """
        entry = self._dragged_entry()
        if entry is None:
            return

        drag = QDrag(self)
        drag.setMimeData(self._drag_mime(entry))
        drag.exec(Qt.DropAction.MoveAction)

    def _can_drag(self) -> bool:
        """Says whether a row of the selection can start a drag.

        A task that stands as a folder can be dragged onto a category, and a
        closed task stands as an archive, which is not a folder to move, so
        its row carries no drag. The selection holds the row the mouse was
        pressed on, so this says whether the move that follows the press has
        anything to carry.
        """
        return any(
            bool(item.flags() & Qt.ItemFlag.ItemIsDragEnabled)
            for item in self.selectedItems()
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Keeps the selection where the press put it.

        A press on a row that cannot be dragged leaves Qt with nothing to
        carry, so the move that follows it turns into a drag-selection, which
        takes the selection to the row under the cursor, away from the row the
        press chose. The move is ignored then, and the selection stays where
        the press put it, with the action bar that belongs to it.
        """
        if event.buttons() and not self._can_drag():
            return

        super().mouseMoveEvent(event)

    def _drag_source(self, event: QDropEvent) -> Path | None:
        """Returns the folder a drag carries, or None when it carries none.

        Args:
            event: the drag or the drop.

        Returns:
            The folder of the task the drag carries, or None.
        """
        data = bytes(event.mimeData().data(_MIME_TYPE).data())
        if not data:
            return None

        return Path(data.decode())

    def _heading_row(self, row: int) -> int:
        """Returns the row of the heading above a task row.

        Args:
            row: the row of the task.

        Returns:
            The row of the heading the task stands under, or -1 when there is
            no heading above it.
        """
        for index in range(row - 1, -1, -1):
            item = self.item(index)
            if item is not None and item.data(_COUNT_ROLE) is None:
                return index

        return -1

    def _category_of(self, row: int) -> tuple[Path | None, int]:
        """Returns the category a task row stands in, and its heading.

        A task row stands in the category of the heading above it, and a tab
        of a category holds no heading, so there the category is the one the
        listing was told about.

        Args:
            row: the row of the task.

        Returns:
            The category the task stands in, and the row of the heading that
            stands for it, which is -1 when the listing holds no heading.
        """
        heading = self._heading_row(row)
        if heading < 0:
            return self._category, -1

        item = self.item(heading)
        category = item.data(_CATEGORY_ROLE) if item is not None else None
        if category is None:
            return self._category, heading

        return Path(category), heading

    def _drop_target(self, pos: QPoint) -> tuple[Path | None, int]:
        """Returns the category a drop at a position would move a task into.

        A heading stands for its own category, and a task row for the one it
        stands under. The empty area below the rows stands for nothing.

        Args:
            pos: the position of the drop, in the viewport.

        Returns:
            The category the task would land in, and the row of the heading
            that stands for it, which is -1 when there is none.
        """
        item = self.itemAt(pos)
        if item is None:
            return None, -1

        row = self.row(item)
        if item.data(_COUNT_ROLE) is None:
            category = item.data(_CATEGORY_ROLE)
            return (Path(category) if category is not None else None), row

        return self._category_of(row)

    def _set_drop_row(self, row: int) -> None:
        """Marks the heading of the category a drop would move a task into.

        Args:
            row: the row of the heading, or -1 when no category is marked.
        """
        if self.delegate.drop_row == row:
            return

        self.delegate.drop_row = row
        self.viewport().update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Takes in a drag that carries a task.

        The drag is taken in wherever it enters, because a drag starts over
        the task it carries, and the rule that keeps a task from landing in
        the category it already stands in would refuse it there; the drag
        would then never reach the category it is aimed at. What a drop lands
        on is decided by the moves that follow.

        Args:
            event: the drag that entered.
        """
        if event.mimeData().hasFormat(_MIME_TYPE):
            event.accept()
            return

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Marks the category a drop would move a task into.

        The heading of the category is marked, so the category the task would
        land in reads as the one under the cursor. A drag over the category
        the task already stands in, or over the empty area, is refused, so
        the cursor says the task cannot go there.

        Args:
            event: the drag that moved over the listing.
        """
        folder = self._drag_source(event)
        category, heading = self._drop_target(event.position().toPoint())

        if folder is None or category is None or folder.parent == category:
            self._set_drop_row(-1)
            event.ignore()
            return

        self._set_drop_row(heading)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """Reports the task of a drag and the category it was dropped on.

        Args:
            event: the drop.
        """
        folder = self._drag_source(event)
        category, _heading = self._drop_target(event.position().toPoint())
        self._set_drop_row(-1)

        if folder is None or category is None or folder.parent == category:
            event.ignore()
            return

        event.accept()
        self.move_requested.emit(folder, category)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Takes the mark off the category when the drag leaves.

        Args:
            event: the drag that left.
        """
        self._set_drop_row(-1)
        event.accept()

    def set_sort(self, column: int, descending: bool) -> None:
        """Orders the rows by a column and shows the indicator on it.

        Args:
            column: the index of the section that was clicked.
            descending: whether the order runs from the last value to the first.
        """
        self.sort_column = column
        self.sort_descending = descending
        self.header.setSortIndicatorShown(True)
        self.header.setSortIndicator(
            column,
            Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder,
        )
        self.apply_sort(column, descending)

    def _click_section(self, column: int) -> None:
        """Sorts by a clicked heading, flipping the order on a second click.

        A first click on a heading, or a click on another one, starts
        ascending; a second click on the same heading turns it around. The clip
        heading carries no order, so clicking it does nothing.

        Args:
            column: the index of the section that was clicked.
        """
        if column == 2:
            return

        descending = column == self.sort_column and not self.sort_descending
        self.set_sort(column, descending)
        self.order_changed.emit(column, descending)

    def apply_sort(self, column: int, descending: bool) -> None:
        """Orders the categories and the task rows by a column and a direction.

        A category is a separator row and the task run under it. The tasks of
        every category are ordered among themselves, and then the categories
        themselves are ordered by the key of the first task of each, so the
        category holding the globally first record comes first and the next
        follows. A category with no task carries no key, so it goes last
        keeping its place among the other empty ones, and two categories whose
        first tasks tie keep the order they had. A task of a tab with no
        separator is a category of its own, ordered the same way. The row that
        was selected stays selected once the rows are back in place.

        Args:
            column: the index of the column to order by.
            descending: whether the order runs from the last value to the first.
        """
        rows = [self.item(index) for index in range(self.count())]
        blocks: list[tuple[QListWidgetItem | None, list[QListWidgetItem]]] = []
        for row in rows:
            if row.data(_COUNT_ROLE) is None:
                blocks.append((row, []))
            elif not blocks:
                # a tab that holds no separator opens on its first task
                blocks.append((None, [row]))
            else:
                blocks[-1][1].append(row)

        for _, tasks in blocks:
            tasks.sort(
                key=lambda row: _order_key(row, column),
                reverse=descending,
            )

        populated = [block for block in blocks if block[1]]
        empty = [block for block in blocks if not block[1]]
        populated.sort(
            key=lambda block: _order_key(block[1][0], column),
            reverse=descending,
        )

        ordered: list[QListWidgetItem] = []
        for separator, tasks in populated + empty:
            if separator is not None:
                ordered.append(separator)
            ordered.extend(tasks)

        selected = self.currentItem()
        while self.count():
            self.takeItem(0)
        for row in ordered:
            self.addItem(row)
        if selected is not None:
            self.setCurrentItem(selected)
            self._sync_action_bar()
        self.fit_task_column()

    def fit_task_column(self) -> None:
        """Widens the task column to hold the longest visible description.

        The width is measured from the font of the rows and clamped between the
        default task width and `_TASK_MAX_WIDTH`; a description past the cap
        still elides. The user owns the width once the section is dragged by
        hand, so this leaves a section they resized alone for the session.
        """
        if self._task_section_user_resized:
            return

        widest = 0
        for index in range(self.count()):
            item = self.item(index)
            entry = item.data(_ENTRY_ROLE)
            if entry is None or item.isHidden():
                continue
            text = helpers.readable_title(entry.title)
            widest = max(
                widest, QFontMetrics(item.font()).horizontalAdvance(text)
            )

        target = max(
            self.header.default_task_width,
            min(widest + 2 * _COLUMN_PADDING, _TASK_MAX_WIDTH),
        )
        if target == self.header.sectionSize(1):
            return

        self._fitting_task_column = True
        self.header.resizeSection(1, target)
        self._fitting_task_column = False

    def column_rect(self, row: QRect, column: int) -> QRect:
        """Returns the rectangle of a column within a row.

        Args:
            row: the row the column belongs to.
            column: the index of the column, from the date on the left.

        Returns:
            The rectangle the column occupies in the row.
        """
        return self.delegate.column_rect(row, column)

    def _columns_changed(self, column: int, _old: int, new: int) -> None:
        """Keeps the cells with the header after a section is resized.

        Args:
            column: the section that was resized.
            _old: the size it had, unused.
            new: the size it was given, unused.
        """
        if column == 1 and not self._fitting_task_column:
            self._task_section_user_resized = True
        self.doItemsLayout()
        self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._place_action_bar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_action_bar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_action_bar()

    def _request(self, signal: SignalInstance) -> None:
        entry = self.selected_entry()
        if entry is not None:
            signal.emit(entry)

    def _request_state(self, new_state: str) -> None:
        """Reports the state picked from the menu of the action bar.

        Args:
            new_state: the state the user chose.
        """
        entry = self.selected_entry()
        if entry is not None:
            self.state_requested.emit(entry, new_state)

    def _deselect(self) -> None:
        """Clears the current row, which hides the action bar with it."""
        self.setCurrentRow(-1)

    def _reminder_scheduler(self) -> ReminderScheduler | None:
        """Returns the scheduler the window carries, or None without one.

        Returns:
            The window's scheduler, or None when the window has none, which
            is the case without a system tray.
        """
        return getattr(self.window(), "reminder_scheduler", None)

    def _reminder_target(self) -> tuple[ReminderScheduler, str, str] | None:
        """Returns the scheduler, the task folder name and its readable title.

        Returns:
            The three values the reminder actions need, or None when no task
            is selected or the window carries no scheduler.
        """
        entry = self.selected_entry()
        scheduler = self._reminder_scheduler()
        if entry is None or scheduler is None:
            return None
        return (
            scheduler,
            entry.file.parent.name,
            helpers.readable_title(entry.title),
        )

    def _add_reminder(self) -> None:
        """Opens the add dialog and stores the reminder it accepted."""
        target = self._reminder_target()
        if target is None:
            return

        scheduler, task, title = target
        dialog = AddReminderDialog(title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            scheduler.add(dialog.due(), dialog.message(), task, title)

    def _show_reminders(self) -> None:
        """Shows the reminders of the selected task in a modal popup."""
        target = self._reminder_target()
        if target is None:
            return

        scheduler, task, title = target
        RemindersDialog(scheduler, task, title, self).exec()

    def _click_separator(self, item: QListWidgetItem) -> None:
        """Reports a clicked category row, dropping the selected task with it.

        A row that carries no category is a task or an archive heading, so it
        says nothing about the destination and the click is left alone. A
        category row is not a task, so the selection and its bar go through the
        same path `Esc` takes before the destination is asked for.

        Args:
            item: the row that was clicked.
        """
        category = item.data(_CATEGORY_ROLE)
        if category is None:
            return

        self._deselect()
        self.destination_requested.emit(category)

    def _sync_action_bar(self) -> None:
        entry = self.selected_entry()

        # the scheduler is assigned after the window is built, so the bar asks
        # the window for it now rather than holding the one of construction
        self.action_bar.set_reminders_available(self._reminder_scheduler() is not None)

        # a row that holds an archive is reopened from it and nothing else,
        # so the bar it gets carries the reopen button alone
        self.action_bar.set_reopening(entry is not None and entry.state == "closed")

        # the bar grows with the reminder buttons, so the room the selected
        # row gives it is read back now that they stand or went away
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.delegate.inset_row = self.currentRow()
        self.doItemsLayout()
        self.viewport().update()

        # Qt lets a heading become the current item, and it still gets no bar
        if entry is None:
            self.action_bar.hide()
            return

        # showing first, then placing: showing a widget with a layout lets the
        # layout resize it to its own idea of a size
        self.action_bar.show()
        self._place_action_bar()

    def _place_action_bar(self) -> None:
        item = self.currentItem()
        if item is None or item.data(_ENTRY_ROLE) is None:
            return

        rect = self.visualItemRect(item)
        band = self.delegate.content_band(rect)
        top = band.bottom() + 1
        self.action_bar.setGeometry(
            rect.left() + _SELECTION_INDICATOR_GAP,
            top,
            self.inset,
            rect.bottom() - top + 1,
        )


class TaskPanel(QWidget):
    """The column headings over the tasks of a category.

    The panel is what a tab holds: the header, and the list under it. The
    header sits in a band of its own above the list rather than over it, so the
    list keeps every row it had, and it owns the geometry of the columns the
    rows are painted with, so each heading sits over its own column.

    Args:
        listing: the list of tasks the headings sit over.
        parent: the widget the panel belongs to.
    """

    def __init__(self, listing: TaskListing, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.listing = listing
        self.header = listing.header

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(listing, 1)
