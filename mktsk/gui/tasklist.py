"""The tasks of a category as a list, with the actions on the selected row."""

import datetime
from itertools import groupby
from typing import NamedTuple

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
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
    QPainter,
    QPalette,
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
    _draw_close,
    _draw_folder,
    _draw_pencil,
    _draw_plus,
    _draw_reopen,
    _draw_state,
    _icon_button,
    _stroked_icon,
)

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_AGE_ROLE = Qt.ItemDataRole.UserRole + 3
_STATE_ROLE = Qt.ItemDataRole.UserRole + 4

_ACTION_BAR_PADDING = 4

# the columns of a task row, from the left: the date of the folder, the task
# itself, the state it is in, how many interventions it carries, and how long
# ago the last was
_HEADINGS = ("Date", "Task", "State", "Interventions", "Last activity")

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
# rect it is handed, just after the action bar. The width of that indicator plus
# a small margin, kept clear between the bar and the text of a selected row, so
# the indicator never touches a glyph
_SELECTION_INDICATOR_GAP = 6

# how the text of a cell sits in the column of it: read from the left and
# centred, so a row of one line looks like the headings above it
_CELL_ALIGNMENT = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
_COUNT_ALIGNMENT = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)


class _Columns(NamedTuple):
    """The widths of the date column and the three right ones of a row."""

    date: int
    state: int
    interventions: int
    activity: int


def _column_widths() -> _Columns:
    """Measures the fixed columns as wide as their contents.

    A heading is the widest thing its column holds, so measuring one keeps the
    column as narrow as it can be and never clipping it. The date column is
    measured from the date itself, like any other column, and is narrowed to
    just that: the room the action bar needs is taken only by the selected row,
    which shifts as a whole, so no column has to carry it. The widths come from
    the font in use rather than from numbers written down, so a font of another
    size needs no constant of its own. They are the initial sizes the header
    starts its sections from; after that the header owns its geometry and the
    cells read it back.

    Returns:
        The width of the date column, of the state one, of the interventions
        one and of the last activity one.
    """
    heading_font = QFont(QApplication.font())
    heading_font.setBold(True)
    headings = QFontMetrics(heading_font)
    body = QFontMetrics(QApplication.font())

    return _Columns(
        body.horizontalAdvance("dd/mm/yyyy") + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[2]) + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[3]) + 2 * _COLUMN_PADDING,
        headings.horizontalAdvance(_HEADINGS[4]) + 2 * _COLUMN_PADDING,
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

    if column == 2:
        return parsing.STATES.index(entry.state)

    if column == 3:
        return entry.interventions

    return entry.last_activity


class _ColumnHeader(QHeaderView):
    """The column headings, and the only source of column geometry.

    Each section is interactive, so a separator can be dragged to give a column
    more or less room, and the delegate reads every column back from here rather
    than measuring one of its own. The date and the three right columns start
    from the widths of their contents, and the task takes the rest of the room
    a row has. No section is held wider than its contents: the action bar is
    taken by the selected row alone, which shifts its cells, so the date is a
    column like any other.
    """

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFixedHeight(height)
        model = QStandardItemModel(0, 5, self)
        for i, text in enumerate(_HEADINGS):
            item = QStandardItem(text)
            if i == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            model.setHorizontalHeaderItem(i, item)
        self.setModel(model)
        self.setSectionsMovable(False)
        self.setSectionsClickable(True)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        cols = _column_widths()
        self.setMinimumSectionSize(cols.state)
        total = cols.state + cols.interventions + cols.activity
        self.resizeSection(0, cols.date)
        self.resizeSection(1, max(total, 100))
        self.resizeSection(2, cols.state)
        self.resizeSection(3, cols.interventions)
        self.resizeSection(4, cols.activity)


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


class _InsetDelegate(QStyledItemDelegate):
    """Paints a row as the columns of the header, keeping the bar clear.

    Every column comes from the header, which owns the geometry: the delegate
    asks it for the position and the size of each section, so a heading never
    sits over a value of another column and dragging a separator moves the cells
    with it. The date and the title come from the task entry, and the state, the
    count and the age reach the delegate in the item roles, which the window
    fills from the task, so painting reads no file and holds no date of its own.
    A row without them is a heading, painted across the whole item.

    With no selection every cell starts at the left edge of the row, laid out
    from the header. The action bar sits on the selected row alone, so that one
    row shifts its whole content right by the room the bar takes and nothing is
    drawn under it; the other rows stay where they were and the columns are left
    unaligned while the selection lasts. Only the selected row hands the style a
    rect narrowed from the left, so the fill and the indicator start after the
    bar and before the shifted content. The date is drawn after the same margin
    the header draws its own text with, so a heading and its value line up.
    Every row keeps the height the bar needs, which stops the list from shifting
    as the selection moves.

    Args:
        inset: the width of the action bar, taken only by the selected row.
        min_height: height a row needs to hold the action bar.
        header: the header the geometry of every column is read from.
    """

    def __init__(self, inset: int, min_height: int, header: _ColumnHeader) -> None:
        super().__init__()
        self.inset = inset
        self.min_height = min_height
        self.header = header
        self.inset_row = -1

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

    def content_rect(self, row: QRect, column: int, selected: bool) -> QRect:
        """Returns the rectangle a cell is painted in, clear of the bar.

        A cell is its column of the row, and the selected row alone carries the
        bar at its left, so the cells of that row are shifted right by the width
        of the bar and the gap left for the selection indicator. A cell the
        shift pushes past the right edge of the row is cut back to what the row
        still holds, so nothing of a row is ever painted outside it; the left
        edge is kept whatever the cut, so a cell that falls entirely past the
        edge keeps the position the shift gave it.

        Args:
            row: the row the column belongs to.
            column: the index of the column, from the date on the left.
            selected: whether the cell belongs to the selected row.

        Returns:
            The rectangle the cell is painted in.
        """
        cell = self.column_rect(row, column)
        if selected:
            cell.translate(self.inset + _SELECTION_INDICATOR_GAP, 0)
        available = row.right() - cell.left() + 1
        if available < cell.width():
            cell.setWidth(max(available, 0))
        return cell

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
            painter.fillRect(
                option.rect,
                _blend(
                    option.palette.color(group, QPalette.ColorRole.Base),
                    option.palette.color(group, QPalette.ColorRole.Text),
                    _SEPARATOR_WEIGHT,
                ),
            )
            super().paint(painter, separator_option, index)
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

        # the bar sits on the selected row alone, so that row has its whole
        # content shifted right by the bar and the indicator gap; only that row
        # hands the style a rect narrowed from the left, so the fill and the
        # indicator start after the bar and before the shifted cells. The other
        # rows stay as they were, so their columns are not aligned across rows
        # while a selection lasts.
        style_option = option
        selected = index.row() == self.inset_row
        if selected:
            style_option = QStyleOptionViewItem(option)
            style_option.rect = QRect(option.rect)
            style_option.rect.setLeft(option.rect.left() + self.inset)
        super().paint(painter, style_option, index)

        padding = self.header.style().pixelMetric(
            QStyle.PixelMetric.PM_HeaderMargin
        )
        entry = index.data(_ENTRY_ROLE)

        painter.save()
        painter.setPen(_cell_pen(option))

        date_cell = self.content_rect(option.rect, 0, selected)
        date_cell.setLeft(date_cell.left() + padding)
        date_text = option.fontMetrics.elidedText(
            _date_cell(entry), Qt.TextElideMode.ElideRight, date_cell.width()
        )
        painter.drawText(
            date_cell,
            _CELL_ALIGNMENT,
            date_text,
        )

        task_cell = self.content_rect(option.rect, 1, selected)
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

        state_cell = self.content_rect(option.rect, 2, selected)
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
        count_cell = self.content_rect(option.rect, 3, selected)
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
        age_cell = self.content_rect(option.rect, 4, selected)
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
        size.setHeight(max(size.height(), self.min_height))
        return size


class TaskListing(QListWidget):
    """A list of tasks with an action bar over the selected row.

    The bar follows the selected row, and shows only when a task is selected.
    Headings are not selectable, so they never get one, and a closed task gets
    a single button, the reopen action, which still reports resume: the other
    actions all speak to a folder. The listing only reports which action was
    asked for, leaving the task logic to the window.
    """

    open_requested = Signal(object)
    resume_requested = Signal(object)
    rename_requested = Signal(object)
    state_requested = Signal(object, str)
    close_requested = Signal(object)
    order_changed = Signal(int, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_bar = _ActionBar(self.viewport())
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.header = _ColumnHeader(
            self.action_bar.minimumSizeHint().height()
        )
        self.delegate = _InsetDelegate(
            self.inset,
            self.action_bar.minimumSizeHint().height(),
            self.header,
        )
        self.sort_column: int | None = None
        self.sort_descending = False
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
        self.currentItemChanged.connect(lambda *_: self._sync_action_bar())
        self.action_bar.hide()

    def selected_entry(self) -> listing.TaskEntry | None:
        """Returns the task of the selected row, or None when none is."""
        item = self.currentItem()
        return item.data(_ENTRY_ROLE) if item else None

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
        ascending; a second click on the same heading turns it around.

        Args:
            column: the index of the section that was clicked.
        """
        descending = column == self.sort_column and not self.sort_descending
        self.set_sort(column, descending)
        self.order_changed.emit(column, descending)

    def apply_sort(self, column: int, descending: bool) -> None:
        """Orders the task rows by a column and a direction.

        The headings of a tab that lists several categories are left where
        they are, so only the task rows move, the group between two headings
        keeping to itself. The row that was selected stays selected once the
        rows are back in place.

        Args:
            column: the index of the column to order by.
            descending: whether the order runs from the last value to the first.
        """
        rows = [self.item(index) for index in range(self.count())]
        ordered: list[QListWidgetItem] = []
        for is_heading, group in groupby(
            rows, key=lambda row: row.data(_COUNT_ROLE) is None
        ):
            run = list(group)
            if not is_heading:
                run.sort(
                    key=lambda row: _order_key(row, column),
                    reverse=descending,
                )
            ordered.extend(run)

        selected = self.currentItem()
        while self.count():
            self.takeItem(0)
        for row in ordered:
            self.addItem(row)
        if selected is not None:
            self.setCurrentItem(selected)
            self._sync_action_bar()

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

    def _sync_action_bar(self) -> None:
        entry = self.selected_entry()

        # a row that holds an archive is reopened from it and nothing else,
        # so the bar it gets carries the reopen button alone
        self.action_bar.set_reopening(entry is not None and entry.state == "closed")

        self.delegate.inset_row = self.currentRow()
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
        self.action_bar.setGeometry(rect.left(), rect.top(), self.inset, rect.height())


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
