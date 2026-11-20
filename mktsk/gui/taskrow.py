"""How a task row is laid out and painted: its columns, its cells and its delegate."""

import datetime
from typing import NamedTuple

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QPainter,
    QPalette,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from mktsk import helpers, listing, parsing, standards

from .icons import (
    _ICON_SIZE,
    _draw_clip,
    _icon_pen,
)
from .selection import (
    _ROW_LINE_REACH,
    _SELECTION_INDICATOR_GAP,
    _SELECTION_INDICATOR_WIDTH,
    _blend,
    _cell_pen,
    _colour_group,
    _paint_selection,
)

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_AGE_ROLE = Qt.ItemDataRole.UserRole + 3
_STATE_ROLE = Qt.ItemDataRole.UserRole + 4
# the category a heading stands for, carried by the `All` headings alone: an
# archive heading lists no folder that a new task could land in, so it has none
_CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 5

# the clip column has no heading: the paperclip says it
_HEADINGS = ("Date", "Task", "", "State", "Interventions", "Last activity")

_COLUMN_PADDING = 6

# extra width reserved in the State column so the state text never overlaps
# the funnel filter button, which sits at the column's right edge. The button
# is wider than the drawn icon because of QToolButton padding.
_STATE_FILTER_BUTTON_SPACE = _ICON_SIZE + _COLUMN_PADDING

# how far a stripe and a category heading blend from Base towards Text
_ZEBRA_WEIGHT = 0.03
_SEPARATOR_WEIGHT = 0.08

# how far the heading of a drop target blends from Base towards Highlight
_DROP_TINT_WEIGHT = 0.35

_DATE_TEXT_LEFT_PADDING = _SELECTION_INDICATOR_GAP  # at least _INDICATOR_WIDTH + 2

# the dot at the right end of the heading of the destination category
_MARKER_RADIUS = 4.0
_MARKER_INSET = 12

_CELL_ALIGNMENT = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
_COUNT_ALIGNMENT = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)


class _Columns(NamedTuple):
    """The widths of the fixed columns of a row, but the task one."""

    date: int
    clip: int
    state: int
    interventions: int
    activity: int


def _heading_width(column: int) -> int:
    """Measures a heading in the bold application font, with its padding.

    Args:
        column: the index of the column, from the date on the left.

    Returns:
        The width the heading needs.
    """
    font = QFont(QApplication.font())
    font.setBold(True)
    return QFontMetrics(font).horizontalAdvance(_HEADINGS[column]) + 2 * _COLUMN_PADDING


def _column_widths() -> _Columns:
    """Measures the fixed columns from the font in use.

    Each starts as wide as its heading; the state column also fits the widest
    state, the clip column fits the icon and two digits, and the date column
    fits a date.

    Returns:
        The width of the date column, of the clip one, of the state one, of the
        interventions one and of the last activity one.
    """
    body = QFontMetrics(QApplication.font())
    widest_state = max(body.horizontalAdvance(state) for state in parsing.STATES)

    return _Columns(
        body.horizontalAdvance("dd/mm/yyyy") + 2 * _COLUMN_PADDING,
        _ICON_SIZE + body.horizontalAdvance("44") + 2 * _COLUMN_PADDING,
        max(
            _heading_width(3),
            widest_state + 2 * _COLUMN_PADDING + _STATE_FILTER_BUTTON_SPACE,
        ),
        _heading_width(4),
        _heading_width(5),
    )


def _state_column_min_width() -> int:
    """Minimum width of the State column so its text never overlaps the
    funnel filter button that sits at the column's right edge.

    Fixed at 66px so the column cannot be dragged narrow enough for the state
    text to collide with the button.
    """
    return 66


def _relative_age(last_activity: datetime.date, today: datetime.date) -> str:
    """Says how long ago a task was worked on: today, yesterday or N days ago.

    A future date reads as today.

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
    """Returns the folder name of a task, or the archive name without its suffix.

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
    """Returns the date of a task as the Date column shows it.

    A name that is not a task name gives its raw prefix.

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
    """Returns the value a row sorts by in a column.

    Dates sort by folder date (other names last), titles without case, states in
    domain order and counts as numbers.

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
    """The column headings, and the single source of column geometry.

    Sections resize by dragging, except the fixed clip column. The task column
    takes the remaining room.
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
        # the task column starts as the rest of the room a row has; auto-width
        # grows it from here up to the cap and never below it. The state counts
        # with its heading, not its widest state, so a wider state column never
        # pushes this start past the cap
        total = cols.clip + _heading_width(3) + cols.interventions + cols.activity
        self.default_task_width = max(total, 100)
        self.resizeSection(0, cols.date)
        self.resizeSection(1, self.default_task_width)
        self.resizeSection(2, cols.clip)
        self.resizeSection(3, cols.state)
        self.resizeSection(4, cols.interventions)
        self.resizeSection(5, cols.activity)


class _TaskDelegate(QStyledItemDelegate):
    """Paints a task row as the columns of the header, and headings across the
    row.

    Column geometry comes from the header and task data from the item roles, so
    painting reads no file. The selected row grows by the action bar band and gets
    the shared selection look: a tint, a rail and short bracket lines.

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
        """Returns the rectangle of a column within a row, from the header
        geometry.

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
        """Returns the column rectangle clipped to the right edge of the row.

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
        return QRect(
            row.left(), row.top(), row.width(), min(row.height(), self.min_height)
        )

    def _paint_row_lines(self, painter: QPainter, option: QStyleOptionViewItem) -> None:
        """Paints the short top and bottom lines that bracket the selected row.

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
        """Clears the text of a task row so the style paints only its background.

        The cells are drawn in `paint`; headings keep their text.

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
                # the destination marker, in the colour of the header icons
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(option.palette.color(QPalette.ColorRole.ButtonText))
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

        # zebra stripes restart under every heading: the parity is counted back
        # to the heading on each paint, so sorting never leaves a stale stripe.
        # A selected row is covered by the selection tint instead
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
        # the style paints the row, then the delegate paints its own selection
        super().paint(painter, option, index)
        if option.state & QStyle.StateFlag.State_Selected:
            _paint_selection(painter, option)
            self._paint_row_lines(painter, option)

        padding = self.header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)
        entry = index.data(_ENTRY_ROLE)

        painter.save()
        pen_colour = _cell_pen(option)
        painter.setPen(pen_colour)

        date_cell = self.content_rect(cells, 0)
        # keep the first glyph clear of the selection rail
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

        # the paperclip and the count, only when the task has attachments
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
        if (
            index.isValid()
            and index.row() == self.inset_row
            and index.data(_ENTRY_ROLE) is not None
        ):
            height += self.accordion_height
        size.setHeight(height)
        return size
