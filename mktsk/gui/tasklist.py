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
    """A list of tasks with an action bar under the selected row.

    Headings are not selectable, and a closed task gets only the reopen button.
    Tasks that stand as folders can be dragged onto a category. The listing
    reports the requested action; the window carries it out.
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
        # the only state shown, or None to show every task
        self._state_filter: str | None = None
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
        # Return and the keypad Enter resume the selected task, like its `+` button
        self.resume_shortcuts: list[QShortcut] = []
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda: self._request(self.resume_requested))
            self.resume_shortcuts.append(shortcut)
        # Ctrl+W closes the selected task into its archive, like its archive button
        self.close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.close_shortcut.activated.connect(self._request_close)

    def selected_entry(self) -> listing.TaskEntry | None:
        """Returns the task of the selected row, or None when none is."""
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        item = selected_items[0]
        return item.data(_ENTRY_ROLE) if item else None

    def select_task(self, path: Path) -> bool:
        """Selects the row of a task, switching to the tab that holds it.

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
        """Returns the task row carrying a path, or None. Headings are skipped.

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
        """Scrolls to the row of a path, looked up again in case a refresh
        replaced it.

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
        """Sets the category the tasks of this listing live in.

        A category tab has no heading to say it, so a drop on its rows needs this.

        Args:
            category: the folder the tasks of this listing live in, or None
                when the listing stands for no category of its own.
        """
        self._category = category

    def _dragged_entry(self) -> listing.TaskEntry | None:
        """Returns the task a drag would carry. Headings and archives are not
        dragged.

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
        """Builds the drag payload: the folder of the task.

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
        """Says whether the selected row can start a drag."""
        return any(
            bool(item.flags() & Qt.ItemFlag.ItemIsDragEnabled)
            for item in self.selectedItems()
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Keeps the selection on a pressed row that cannot be dragged.

        Otherwise Qt turns the move into a drag-selection that moves it.
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
        """Returns the category a task row stands in, and the row of its heading.

        Without a heading, the category is the one set with `set_category`.

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
        """Accepts any drag that carries a task; `dragMoveEvent` decides where it
        may land.

        Args:
            event: the drag that entered.
        """
        if event.mimeData().hasFormat(_MIME_TYPE):
            event.accept()
            return

        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Marks the category under the cursor, refusing the task's own category.

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
        """Sorts by a clicked heading; a second click reverses. The clip column
        does not sort.

        Args:
            column: the index of the section that was clicked.
        """
        if column == 2:
            return

        descending = column == self.sort_column and not self.sort_descending
        self.set_sort(column, descending)
        self.order_changed.emit(column, descending)

    def apply_sort(self, column: int, descending: bool) -> None:
        """Orders the tasks of each category by a column, then the categories.

        Categories follow the key of their first task; empty ones go last. The
        selection is kept.

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
        # rows taken out and put back lose their hidden flag
        self.set_state_filter(self._state_filter)
        self.fit_task_column()

    def set_state_filter(self, state: str | None) -> None:
        """Shows only the tasks in a state, or every task for None.

        A heading left without a visible task hides with them, and a selected
        task that hides is deselected.

        Args:
            state: the state to show, or None for every state.
        """
        self._state_filter = state
        heading: QListWidgetItem | None = None
        heading_visible = False
        for index in range(self.count()):
            item = self.item(index)
            entry = item.data(_ENTRY_ROLE)
            if entry is None:
                if heading is not None:
                    heading.setHidden(state is not None and not heading_visible)
                heading, heading_visible = item, False
                continue
            hidden = state is not None and entry.state != state
            item.setHidden(hidden)
            heading_visible = heading_visible or not hidden
        if heading is not None:
            heading.setHidden(state is not None and not heading_visible)

        current = self.currentItem()
        if current is not None and current.isHidden():
            self._deselect()

    def fit_task_column(self) -> None:
        """Widens the task column to the longest visible title, up to
        `_TASK_MAX_WIDTH`.

        Stops once the user resizes the column by hand.
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

    def _request_close(self) -> None:
        """Reports a close of the selected task, unless it is already closed."""
        entry = self.selected_entry()
        if entry is not None and entry.state != "closed":
            self.close_requested.emit(entry)

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
        """Makes a clicked category heading the destination and drops the selected
        task.

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
    """What a tab holds: the column header above the task list.

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
