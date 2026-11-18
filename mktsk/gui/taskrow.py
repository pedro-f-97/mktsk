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

# the columns of a task row, from the left: the date of the folder, the task
# itself, a paperclip and the number of attachments it carries when it has any,
# the state it is in, how many interventions it carries, and how long ago the
# last was. The clip heading carries no name, because the paperclip says it
_HEADINGS = ("Date", "Task", "", "State", "Interventions", "Last activity")

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

_DATE_TEXT_LEFT_PADDING = _SELECTION_INDICATOR_GAP  # at least _INDICATOR_WIDTH + 2

# the marker a heading carries when it stands for the destination: a small dot
# at the right end of the row, clear of the name the style draws from the left
_MARKER_RADIUS = 4.0
_MARKER_INSET = 12

# how the text of a cell sits in the column of it: read from the left and
# centred, so a row of one line looks like the headings above it
_CELL_ALIGNMENT = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
_COUNT_ALIGNMENT = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)


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
