"""The reminders of a task, as a list sorted by when they are due."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from .reminders_scheduler import ReminderScheduler

_WHEN_FORMAT = "%d/%m/%Y %H:%M"
_WHEN_COLUMN = 0
_MESSAGE_COLUMN = 1
_TASK_COLUMN = 2
_WHEN_WIDTH = 130
_DELETE_WIDTH = 24
_DELETE_TEXT = "×"
_DELETE_TOOLTIP = "Delete"
_REMINDER_ROLE = Qt.ItemDataRole.UserRole + 1


class RemindersList(QTreeWidget):
    """The reminders of one task, or every reminder, sorted by due.

    The last column carries a `×` that removes the reminder of its row and
    nothing else, so a click anywhere else in a row leaves the store alone.
    The list follows `scheduler.changed`, so a reminder added or removed
    anywhere shows up without another call.

    Args:
        scheduler: the scheduler the reminders are read from and removed
            through.
        task: the task folder name to filter by, or None for every reminder.
        parent: the widget the list belongs to.
    """

    def __init__(
        self,
        scheduler: ReminderScheduler,
        task: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scheduler = scheduler
        self.task = task
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)

        headings = ["When", "Message"]
        if task is None:
            headings.append("Task")
        headings.append("")
        self.setColumnCount(len(headings))
        self.setHeaderLabels(headings)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_MESSAGE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(_WHEN_COLUMN, _WHEN_WIDTH)
        self.setColumnWidth(self.columnCount() - 1, _DELETE_WIDTH)

        scheduler.changed.connect(self.refresh)
        self.itemClicked.connect(self._clicked)
        self.refresh()

    def refresh(self) -> None:
        """Rebuilds the rows from the scheduler, sorted by due."""
        reminders = (
            self.scheduler.reminders()
            if self.task is None
            else self.scheduler.for_task(self.task)
        )
        self.clear()
        for reminder in sorted(reminders, key=lambda reminder: reminder.due):
            self._add_row(reminder)

    def _add_row(self, reminder) -> None:
        """Adds the row of one reminder, with its delete cell last.

        Args:
            reminder: the reminder to show.
        """
        row = QTreeWidgetItem(self)
        row.setText(_WHEN_COLUMN, reminder.due.strftime(_WHEN_FORMAT))
        # a reminder without a message still says what it is about
        row.setText(_MESSAGE_COLUMN, reminder.message or reminder.title)
        if self.task is None:
            row.setText(_TASK_COLUMN, reminder.title)

        delete = self.columnCount() - 1
        row.setText(delete, _DELETE_TEXT)
        row.setToolTip(delete, _DELETE_TOOLTIP)
        row.setData(_WHEN_COLUMN, _REMINDER_ROLE, reminder.id)

    def _clicked(self, row: QTreeWidgetItem, column: int) -> None:
        """Removes the reminder whose delete cell was clicked, and nothing else.

        Args:
            row: the row that was clicked.
            column: the column the click landed in.
        """
        if column != self.columnCount() - 1:
            return

        self.scheduler.remove(row.data(_WHEN_COLUMN, _REMINDER_ROLE))
