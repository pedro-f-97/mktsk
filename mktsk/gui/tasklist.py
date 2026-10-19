"""The tasks of a category as a list, with the actions on the selected row."""

import datetime
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QKeySequence,
    QPainter,
    QPalette,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mktsk import helpers, listing, parsing, standards

from .icons import (
    _ICON_SIZE,
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

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_AGE_ROLE = Qt.ItemDataRole.UserRole + 3
_STATE_ROLE = Qt.ItemDataRole.UserRole + 4
# the category a heading stands for, carried by the `All` headings alone: an
# archive heading lists no folder that a new task could land in, so it has none
_CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 5

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

# the windows11 style paints its selection indicator at the left edge of the
# rect it is handed. The width of that indicator plus a small margin, which
# indents the action bar of the auxiliary row, so the marker of the selection
# stays visible at the left edge of the row and the bar never covers it
_SELECTION_INDICATOR_WIDTH = 3
_SELECTION_INDICATOR_GAP = _SELECTION_INDICATOR_WIDTH + 3
_DATE_TEXT_LEFT_PADDING = _SELECTION_INDICATOR_GAP  # at least _INDICATOR_WIDTH + 2

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
        for button in self.buttons():
            layout.addWidget(button)

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

    def set_reopening(self, reopening: bool) -> None:
        """Offers reopen alone for a row that holds a closed task.

        The other four actions all speak to a folder, and only reopening
        makes the folder stand again, so they are left out until then. The
        button that carries resume carries the reopen icon and tooltip while
        it stands for reopening, because reopening an archived task is not
        adding a note for today; putting it back restores both.

        Args:
            reopening: True when the selected row holds a closed task.
        """
        for button in (
            self.open_button,
            self.rename_button,
            self.state_button,
            self.close_button,
        ):
            button.setVisible(not reopening)

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


# the pen of a selected cell, per style, palette group and selection: a style
# paints the same selection for as long as the application runs, so what it
# paints is read back once rather than on every paint
_PEN_CACHE: dict[tuple[str, QPalette.ColorGroup, bool], QColor] = {}


def _painted_background(option: QStyleOptionViewItem) -> QColor:
    """Reads back the colour the style fills a selected row with.

    The fill of a selected row is not always a colour the palette holds: a
    platform style may paint one of its own, so the only way to know what the
    text is drawn on is to paint it. The style is asked for the item panel over
    an image that starts as the base colour, and the centre of the row is read
    back, clear of the indicator some styles draw at its left edge. A style
    that paints nothing leaves the base colour, which is then what the text is
    measured against.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour the style fills the middle of the row with.
    """
    group = _colour_group(option.state)
    width = max(option.rect.width(), 1)
    height = max(option.rect.height(), 1)
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(option.palette.color(group, QPalette.ColorRole.Base))
    sampled = QStyleOptionViewItem(option)
    sampled.rect = QRect(0, 0, width, height)
    style = (
        option.widget.style() if option.widget is not None else QApplication.style()
    )
    painter = QPainter(image)
    style.drawPrimitive(
        QStyle.PrimitiveElement.PE_PanelItemViewItem, sampled, painter, option.widget
    )
    painter.end()

    return image.pixelColor(width // 2, height // 2)


def _cell_pen(option: QStyleOptionViewItem) -> QColor:
    """Returns the colour of the text of a cell, paired with its background.

    An unselected row keeps the Text of the group its state belongs to. A
    selected one is drawn on whatever the style filled it with, so the text is
    the HighlightedText or the Text of that group, whichever holds better
    against the colour read back from the style: both come from the palette and
    the better contrast wins, so no colour is written down here. The choice is
    remembered per style, group and selection, because the style does not
    change what it paints while the application runs.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour the row is drawn in.
    """
    group = _colour_group(option.state)
    palette = option.palette

    if not (option.state & QStyle.StateFlag.State_Selected):
        return palette.color(group, QPalette.ColorRole.Text)

    style = (
        option.widget.style() if option.widget is not None else QApplication.style()
    )
    key = (style.objectName(), group, True)
    pen = _PEN_CACHE.get(key)
    if pen is not None:
        return pen

    background = _painted_background(option)
    highlighted = palette.color(group, QPalette.ColorRole.HighlightedText)
    plain = palette.color(group, QPalette.ColorRole.Text)
    pen = (
        plain
        if _contrast_ratio(plain, background) > _contrast_ratio(highlighted, background)
        else highlighted
    )
    _PEN_CACHE[key] = pen

    return pen


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
    style paints the whole row of a selection, indicator included, from its left
    edge, and the bar is indented past that indicator rather than the cells
    being pushed right. The date is drawn after the same margin the header
    draws its own text with, so a heading and its value line up. Every row keeps
    the height the bar needs, which stops the list from shifting as the
    selection moves.

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

        # the row background and the selection are the style's, as they are for
        # any view. A stripe fills the whole row before the style paints, so
        # hover and the native look still draw on top; a selected row gets no
        # stripe of its own, because the style paints its selection. The stripes
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
        # the style paints the whole row, indicator included, from its left edge
        super().paint(painter, option, index)

        padding = self.header.style().pixelMetric(
            QStyle.PixelMetric.PM_HeaderMargin
        )
        entry = index.data(_ENTRY_ROLE)

        painter.save()
        pen_colour = _cell_pen(option)
        painter.setPen(pen_colour)

        cells = self.content_band(option.rect) if selected else option.rect
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
    """

    open_requested = Signal(object)
    resume_requested = Signal(object)
    rename_requested = Signal(object)
    state_requested = Signal(object, str)
    close_requested = Signal(object)
    order_changed = Signal(int, bool)
    destination_requested = Signal(str)

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
        self.setItemDelegate(self.delegate)
        self.header.sectionResized.connect(self._columns_changed)
        self.header.sectionClicked.connect(self._click_section)
        self.horizontalScrollBar().valueChanged.connect(self.header.setOffset)

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

    def set_destination(self, directory: Path | None) -> None:
        """Points the marker at the category a new task would land in.

        Args:
            directory: the selected category, or None with the base directory.
        """
        self.delegate.destination = str(directory) if directory is not None else None
        self.viewport().update()

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

        # a row that holds an archive is reopened from it and nothing else,
        # so the bar it gets carries the reopen button alone
        self.action_bar.set_reopening(entry is not None and entry.state == "closed")

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
