"""The tasks of a category as a list, with the actions on the selected row."""

from pathlib import Path

from PySide6.QtCore import (
    QMimeData,
    QPoint,
    QRect,
    Qt,
    QTimer,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFontMetrics,
    QKeySequence,
    QMouseEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mktsk import helpers, listing, standards

from .actionbar import (
    _ACTION_BAR_PADDING,
    _ActionBar,
)
from .reminders_scheduler import ReminderScheduler
from .reminders_ui import AddReminderDialog, RemindersDialog
from .selection import (
    _SELECTION_INDICATOR_GAP,
)
from .taskrow import (
    _CATEGORY_ROLE,
    _COLUMN_PADDING,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _ColumnHeader,
    _order_key,
    _TaskDelegate,
)

# the mime type a drag of a task carries: the folder of the task, so a drop
# knows which task it moves without reading anything, and a drag from
# elsewhere is never taken for one of ours
_MIME_TYPE = "application/x-mktsk-task"

# maximum width of the task column in logical pixels
_TASK_MAX_WIDTH = 480


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
        self.action_bar.reminders_menu.actions()[0].triggered.connect(
            self._add_reminder
        )
        self.action_bar.reminders_menu.actions()[1].triggered.connect(
            self._show_reminders
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
