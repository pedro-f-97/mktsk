"""The tasks of a category as a list, with the actions on the selected row."""

import datetime
from typing import NamedTuple

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mktsk import listing, parsing

from .icons import _draw_folder, _draw_pencil, _draw_plus, _draw_state, _icon_button

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_AGE_ROLE = Qt.ItemDataRole.UserRole + 3
_STATE_ROLE = Qt.ItemDataRole.UserRole + 4

_ACTION_BAR_PADDING = 4

# the columns of a task row, from the left: the task itself, the state it is
# in, how many interventions it carries, and how long ago the last was
_HEADINGS = ("Task", "State", "Interventions", "Last activity")

# the states the change-state action offers: `closed` only comes from closing
# the task, which is a different operation
_OFFERED_STATES = tuple(state for state in parsing.STATES if state != "closed")

_COLUMN_PADDING = 6

# how a row too narrow for all the columns shares what is left: the task takes
# one share of four, the state and the two columns of its activity one each
_TASK_SHARE = 1
_SHARES = _TASK_SHARE + 3

# how the text of a cell sits in the column of it: read from the left and
# centred, so a row of one line looks like the headings above it
_CELL_ALIGNMENT = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


class _Columns(NamedTuple):
    """The widths of the three right columns of a row."""

    state: int
    interventions: int
    activity: int


def _column_widths() -> _Columns:
    """Measures the right columns as wide as the headings over them.

    A heading is the widest thing its column holds, so measuring one keeps the
    column as narrow as it can be and never clipping it. The widths come from
    the font in use rather than from numbers written down, so a font of another
    size needs no constant of its own, and the header and the rows ask here and
    get the same widths.

    Returns:
        The width of the state column, of the interventions one and of the last
        activity one.
    """
    font = QFont(QApplication.font())
    font.setBold(True)
    metrics = QFontMetrics(font)

    return _Columns(
        metrics.horizontalAdvance(_HEADINGS[1]) + 2 * _COLUMN_PADDING,
        metrics.horizontalAdvance(_HEADINGS[2]) + 2 * _COLUMN_PADDING,
        metrics.horizontalAdvance(_HEADINGS[3]) + 2 * _COLUMN_PADDING,
    )


def _column_rects(row: QRect, columns: _Columns) -> tuple[QRect, QRect, QRect, QRect]:
    """Splits a row into the task, the state, the interventions and the activity.

    The header above the list and the rows themselves both ask here, so a
    heading never sits over a value of another column. The three right columns
    are as wide as the headings over them and the task takes the rest. A row too
    narrow for all four shares what is left by weight, the task counting a
    share against one for each of the other columns, because a row showing the
    numbers of a task without the task itself says nothing. No column is ever
    given a negative width, whatever the row is.

    Args:
        row: the row to split.
        columns: the widths of the three right columns.

    Returns:
        The four columns, from the task on the left to the last activity on the
        right, each as tall as the row.
    """
    available = max(0, row.width() - 2 * _COLUMN_PADDING)
    needed = columns.state + columns.interventions + columns.activity

    if available * (_SHARES - _TASK_SHARE) >= needed * _SHARES:
        task_width = available - needed
        state = columns.state
        interventions = columns.interventions
        activity = columns.activity
    else:
        task_width = available * _TASK_SHARE // _SHARES
        room = available - task_width
        state = min(columns.state, room * columns.state // needed)
        interventions = min(
            columns.interventions, room * columns.interventions // needed
        )
        activity = min(columns.activity, room - state - interventions)

    last = max(row.left(), row.right() - _COLUMN_PADDING - activity + 1)
    middle = max(row.left(), last - interventions)
    first = max(row.left(), middle - state)

    return (
        QRect(
            row.left() + _COLUMN_PADDING,
            row.top(),
            max(0, first - row.left() - _COLUMN_PADDING),
            row.height(),
        ),
        QRect(first, row.top(), max(0, state), row.height()),
        QRect(middle, row.top(), max(0, interventions), row.height()),
        QRect(last, row.top(), max(0, activity), row.height()),
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


class _ColumnHeader(QFrame):
    """The names of the columns of the task list, above it.

    The headings are placed by arithmetic against the width of a row, from the
    same `_column_rects` the rows are painted with, so a heading never sits over
    a value of another column. The row is not the header itself but the list
    under it, which is narrower when it shows a scrollbar, so the width comes
    from `set_row_width` rather than from the width of the header.
    """

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = _column_widths()
        self.row_width = 0
        labels = [_heading(text, self) for text in _HEADINGS]
        (
            self.task_label,
            self.state_label,
            self.interventions_label,
            self.activity_label,
        ) = labels

        self.rule = QFrame(self)
        self.rule.setFrameShape(QFrame.Shape.HLine)
        self.rule.setFixedHeight(1)

        # the band is as tall as a row, so the headings line up with the rows
        self.setFixedHeight(height)

    def labels(self) -> tuple[QLabel, QLabel, QLabel, QLabel]:
        """Returns the four headings, from the task on the left."""
        return (
            self.task_label,
            self.state_label,
            self.interventions_label,
            self.activity_label,
        )

    def set_row_width(self, width: int) -> None:
        """Places the headings over a row of the given width.

        Args:
            width: the width of a row of the list under the header.
        """
        self.row_width = width
        self._place()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place()

    def _place(self) -> None:
        """Moves each heading over its own column of the row below."""
        row = QRect(0, 0, self.row_width, self.height())
        columns = _column_rects(row, self.columns)
        for label, column in zip(self.labels(), columns, strict=True):
            label.setGeometry(column)
        self.rule.setGeometry(0, self.height() - 1, self.width(), 1)


def _heading(text: str, parent: QWidget) -> QLabel:
    """Builds a column heading, bold the way a category heading is."""
    label = QLabel(text, parent)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


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
        """Returns the four action buttons, in order."""
        return (
            self.open_button,
            self.resume_button,
            self.rename_button,
            self.state_button,
        )


def _cell_pen(option: QStyleOptionViewItem) -> QColor:
    """Returns the colour of the text of a cell, which follows the selection.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour the row is drawn in.
    """
    role = (
        QPalette.ColorRole.HighlightedText
        if option.state & QStyle.StateFlag.State_Selected
        else QPalette.ColorRole.Text
    )

    return option.palette.color(role)


class _InsetDelegate(QStyledItemDelegate):
    """Paints a row as the columns of the list, keeping the bar clear.

    The right columns are painted from `_column_rects`, the same arithmetic
    the header above them is placed by, so a heading never sits over a value of
    another column. The state, the count and the age reach the delegate in the
    item roles, which the window fills from the task, so painting reads no file
    and holds no date of its own. A row without them is a heading, which is
    painted where it stands.

    Only the selected row is inset, so the space for the buttons appears when the
    row is clicked and is given back when the selection goes. Every row keeps the
    height the bar needs, which stops the list from shifting as the selection
    moves.

    Args:
        inset: width reserved on the left of the selected row.
        min_height: height a row needs to hold the action bar.
        columns: the widths of the three right columns.
    """

    def __init__(self, inset: int, min_height: int, columns: _Columns) -> None:
        super().__init__()
        self.inset = inset
        self.min_height = min_height
        self.columns = columns
        self.inset_row = -1

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        option.rect = QRect(option.rect)
        if index.row() == self.inset_row:
            option.rect.adjust(self.inset, 0, 0, 0)

        task, state, interventions, activity = _column_rects(option.rect, self.columns)
        count = index.data(_COUNT_ROLE)
        if count is None:
            super().paint(painter, option, index)
            return

        # the task keeps its own text, elided into the column it has left
        option.text = option.fontMetrics.elidedText(
            index.data(Qt.ItemDataRole.DisplayRole),
            Qt.TextElideMode.ElideRight,
            task.width(),
        )
        super().paint(painter, option, index)

        painter.save()
        painter.setPen(_cell_pen(option))
        painter.drawText(state, _CELL_ALIGNMENT, index.data(_STATE_ROLE))
        painter.drawText(interventions, _CELL_ALIGNMENT, count)
        painter.drawText(activity, _CELL_ALIGNMENT, index.data(_AGE_ROLE))
        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), self.min_height))
        if index.row() == self.inset_row:
            size.setWidth(size.width() + self.inset)
        return size


class TaskListing(QListWidget):
    """A list of tasks with an action bar over the selected row.

    The bar follows the selected row, and shows only when a task is selected.
    Headings are not selectable, so they never get one. The listing only reports
    which action was asked for, leaving the task logic to the window.
    """

    open_requested = Signal(object)
    resume_requested = Signal(object)
    rename_requested = Signal(object)
    state_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_bar = _ActionBar(self.viewport())
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.delegate = _InsetDelegate(
            self.inset,
            self.action_bar.minimumSizeHint().height(),
            _column_widths(),
        )
        self.setItemDelegate(self.delegate)

        self.action_bar.open_button.clicked.connect(
            lambda: self._request(self.open_requested)
        )
        self.action_bar.resume_button.clicked.connect(
            lambda: self._request(self.resume_requested)
        )
        self.action_bar.rename_button.clicked.connect(
            lambda: self._request(self.rename_requested)
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
        self.delegate.inset_row = self.currentRow()
        self.viewport().update()

        if self.selected_entry() is None:
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

    The panel is what a tab holds: the headings, and the list under them. The
    headings sit in a band of their own above the list rather than over it, so
    the list keeps every row it had, and the headings are placed from the same
    arithmetic the rows are painted with, so each sits over its own column.

    Args:
        listing: the list of tasks the headings sit over.
        parent: the widget the panel belongs to.
    """

    def __init__(self, listing: TaskListing, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.listing = listing
        self.header = _ColumnHeader(listing.delegate.min_height, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(listing, 1)

        # the rows lose their width to a scrollbar, so the headings have to be
        # placed again every time the list is given another width
        listing.viewport().installEventFilter(self)
        self._place_header()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Puts the headings back over the rows when the list is resized.

        Args:
            watched: the widget the event went to.
            event: the event that arrived.

        Returns:
            What the panel would have done with it, which is nothing.
        """
        if event.type() == QEvent.Type.Resize:
            self._place_header()

        return super().eventFilter(watched, event)

    def _place_header(self) -> None:
        """Places the headings over the width of a row of the list."""
        self.header.set_row_width(self.listing.viewport().width())
