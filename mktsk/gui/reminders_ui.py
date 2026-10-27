"""The reminders of a task: the list, adding one, and the popup that holds it.

The scheduler carries every store operation, so this module only asks it for
the reminders, adds to it and removes from it, and leaves the task logic and
the file itself where they are.
"""

from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QDateTime, Qt, QTime
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
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


def _next_whole_hour() -> datetime:
    """The first whole hour after now, which the dialog opens with."""
    now = datetime.now()  # noqa: DTZ005
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


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


class AddReminderDialog(QDialog):
    """Asks when a reminder is due and what it says.

    The due time opens at the next whole hour, and `OK` stands enabled only
    while the chosen minute is still ahead, because a past reminder would fire
    at once and remind no one.

    Args:
        task_title: the readable title of the task, used in the dialog title.
        parent: the widget the dialog is shown over.
    """

    def __init__(self, task_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add reminder - {task_title}")
        self.task_title = task_title

        self.date_edit = QDateTimeEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        next_hour = _next_whole_hour()
        # the value is built from its parts rather than from a Python datetime,
        # because a patched `datetime` module no longer converts that way
        self.date_edit.setDateTime(
            QDateTime(
                QDate(next_hour.year, next_hour.month, next_hour.day),
                QTime(next_hour.hour, next_hour.minute),
            )
        )
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Message (optional)")

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)

        layout = QVBoxLayout(self)
        layout.addWidget(self.date_edit)
        layout.addWidget(self.message_input)
        layout.addWidget(self.buttons)

        self.date_edit.dateTimeChanged.connect(self._update_ok)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._update_ok()

    def _update_ok(self) -> None:
        """Enables OK while the chosen minute is in the future."""
        self.ok_button.setEnabled(self.due() > datetime.now())  # noqa: DTZ005

    def due(self) -> datetime:
        """The chosen due time, naive and to the minute."""
        chosen = self.date_edit.dateTime().toPython()
        return chosen.replace(tzinfo=None, second=0, microsecond=0)

    def message(self) -> str:
        """The message typed, stripped of the surrounding whitespace."""
        return self.message_input.text().strip()


class RemindersDialog(QDialog):
    """The reminders of one task, in a modal popup.

    Args:
        scheduler: the scheduler the reminders are read from and removed
            through.
        task: the task folder name whose reminders are listed.
        task_title: the readable title of the task, used in the dialog title.
        parent: the widget the dialog is shown over.
    """

    def __init__(
        self,
        scheduler: ReminderScheduler,
        task: str,
        task_title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Reminders - {task_title}")
        self.setModal(True)

        self.reminders_list = RemindersList(scheduler, task, self)
        self.close_button = QPushButton("Close")

        layout = QVBoxLayout(self)
        layout.addWidget(self.reminders_list)
        layout.addWidget(self.close_button)

        self.close_button.clicked.connect(self.accept)
