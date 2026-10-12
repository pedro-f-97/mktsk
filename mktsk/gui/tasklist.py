"""The tasks of a category as a list, with the actions on the selected row."""

import datetime
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
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mktsk import listing, parsing

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

# the columns of a task row, from the left: the task itself, the state it is
# in, how many interventions it carries, and how long ago the last was
_HEADINGS = ("Task", "State", "Interventions", "Last activity")

# the states the change-state action offers: `closed` only comes from closing
# the task, which is a different operation
_OFFERED_STATES = tuple(state for state in parsing.STATES if state != "closed")

_COLUMN_PADDING = 6

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
    size needs no constant of its own. They are the initial sizes the header
    starts its sections from; after that the header owns its geometry and the
    cells read it back.

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


class _ColumnHeader(QHeaderView):
    """The column headings, and the only source of column geometry.

    Each section is interactive, so a separator can be dragged to give a column
    more or less room, and the delegate reads every column back from here rather
    than measuring one of its own. The three right columns start from the widths
    of their headings, and the task takes the rest of the room a row has.
    """

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFixedHeight(height)
        model = QStandardItemModel(0, 4, self)
        for i, text in enumerate(_HEADINGS):
            item = QStandardItem(text)
            if i == 2:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            model.setHorizontalHeaderItem(i, item)
        self.setModel(model)
        self.setSectionsMovable(False)
        self.setSectionsClickable(False)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        cols = _column_widths()
        self.setMinimumSectionSize(cols.state)
        total = cols.state + cols.interventions + cols.activity
        self.resizeSection(0, max(total, 100))
        self.resizeSection(1, cols.state)
        self.resizeSection(2, cols.interventions)
        self.resizeSection(3, cols.activity)


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


def _selection_colour(option: QStyleOptionViewItem) -> QColor:
    """Returns the colour the delegate fills a selected row with.

    It is the Highlight of the palette group the state belongs to. The
    delegate paints this fill itself rather than leaving it to the style,
    because a platform style may paint a selection the palette does not
    describe, and then the text would be chosen against a colour that is not
    what the row is made of. Painting it here keeps the fill and the pen that
    is measured against it the same colour.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour a selected row is filled with.
    """
    return option.palette.color(
        _colour_group(option.state), QPalette.ColorRole.Highlight
    )


def _cell_pen(option: QStyleOptionViewItem) -> QColor:
    """Returns the colour of the text of a cell, paired with its background.

    An unselected row keeps the Text of the group its state belongs to. A
    selected one is filled with `_selection_colour`, and the text is the
    HighlightedText or the Text of that group, whichever holds better against
    the fill: both come from the palette and the better contrast wins, so no
    colour is written down here.

    Args:
        option: what the row is painted from, holding its palette and its state.

    Returns:
        The colour the row is drawn in.
    """
    group = _colour_group(option.state)
    palette = option.palette

    if not (option.state & QStyle.StateFlag.State_Selected):
        return palette.color(group, QPalette.ColorRole.Text)

    background = _selection_colour(option)
    highlighted = palette.color(group, QPalette.ColorRole.HighlightedText)
    plain = palette.color(group, QPalette.ColorRole.Text)

    if _contrast_ratio(plain, background) > _contrast_ratio(highlighted, background):
        return plain

    return highlighted


class _InsetDelegate(QStyledItemDelegate):
    """Paints a row as the columns of the header, keeping the bar clear.

    Every column comes from the header, which owns the geometry: the delegate
    asks it for the position and the size of each section, so a heading never
    sits over a value of another column and dragging a separator moves the cells
    with it. The state, the count and the age reach the delegate in the item
    roles, which the window fills from the task, so painting reads no file and
    holds no date of its own. A row without them is a heading, painted across
    the whole item.

    Only the selected row is inset, so the space for the buttons appears when the
    row is clicked and is given back when the selection goes. Every row keeps the
    height the bar needs, which stops the list from shifting as the selection
    moves.

    Args:
        inset: width reserved on the left of the selected row.
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
            column: the index of the column, from the task on the left.

        Returns:
            The rectangle the column occupies in the row.
        """
        return QRect(
            row.left() + self.header.sectionPosition(column),
            row.top(),
            self.header.sectionSize(column),
            row.height(),
        )

    def initStyleOption(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Fills the option the style paints a row from, without its text.

        The base class fills option.text from the display role every time it
        paints, so emptying it in paint is lost on the copy paint is handed;
        a task row has to lose its text here, where that copy is filled. The
        style then draws the row background and nothing else, and the four
        cells are drawn by paint, each in its own column. A heading keeps its
        text, so the style still paints it across the row.

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
            super().paint(painter, option, index)
            return

        # the selection fill is painted here rather than left to the style,
        # because a platform style may fill a selected row with a colour the
        # palette does not describe: the cells would then be drawn on a
        # background their pen was not chosen against. The style is handed an
        # option without the selection, so it draws no fill of its own over
        # this one and the focus rectangle still comes from it. Its text is
        # empty, emptied by initStyleOption, so the cells below are the whole
        # text of the row.
        style_option = option
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, _selection_colour(option))
            style_option = QStyleOptionViewItem(option)
            style_option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, style_option, index)

        task = self.column_rect(option.rect, 0)
        if index.row() == self.inset_row:
            task.setLeft(task.left() + self.inset)

        painter.save()
        painter.setPen(_cell_pen(option))
        painter.drawText(
            task,
            _CELL_ALIGNMENT,
            option.fontMetrics.elidedText(
                index.data(Qt.ItemDataRole.DisplayRole),
                Qt.TextElideMode.ElideRight,
                task.width(),
            ),
        )
        painter.drawText(
            self.column_rect(option.rect, 1), _CELL_ALIGNMENT, index.data(_STATE_ROLE)
        )
        painter.drawText(
            self.column_rect(option.rect, 2),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            count,
        )
        painter.drawText(
            self.column_rect(option.rect, 3), _CELL_ALIGNMENT, index.data(_AGE_ROLE)
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_bar = _ActionBar(self.viewport())
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.header = _ColumnHeader(self.action_bar.minimumSizeHint().height())
        self.delegate = _InsetDelegate(
            self.inset,
            self.action_bar.minimumSizeHint().height(),
            self.header,
        )
        self.setItemDelegate(self.delegate)
        self.header.sectionResized.connect(self._columns_changed)
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

    def column_rect(self, row: QRect, column: int) -> QRect:
        """Returns the rectangle of a column within a row.

        Args:
            row: the row the column belongs to.
            column: the index of the column, from the task on the left.

        Returns:
            The rectangle the column occupies in the row.
        """
        return self.delegate.column_rect(row, column)

    def _columns_changed(self) -> None:
        """Keeps the cells with the header after a section is resized."""
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
