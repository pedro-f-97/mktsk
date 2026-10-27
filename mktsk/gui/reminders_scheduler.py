"""Polls the reminders store and fires due ones through the tray icon.

No buttons, dialogs or lists: the scheduler only reminds and reports that
something changed through its `changed` signal.
"""

from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from mktsk.reminders import (
    Reminder,
    add,
    for_task,
    load,
    pop_due,
    remove,
)

_POLL_INTERVAL_MS = 30_000
_STAGGER_MS = 1_500
_TRAY_TITLE = "mktsk"


class ReminderScheduler(QObject):
    """Fires due reminders through the tray on a 30 second poll.

    Attributes:
        changed: emitted whenever at least one reminder was fired, or a
            reminder is added or removed.
    """

    changed = Signal()

    def __init__(self, tray, path, parent=None) -> None:
        super().__init__(parent)
        self._tray = tray
        self._path = path
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.check)

    def start(self) -> None:
        """Starts the 30 second poll."""
        self._timer.start()

    def stop(self) -> None:
        """Stops the poll."""
        self._timer.stop()

    def check(self, now: datetime | None = None) -> None:
        """Fires the reminders due at or before `now`, staggered 1.5 s apart.

        The first notification is immediate; the rest are scheduled with
        `QTimer.singleShot`. Emits `changed` only when at least one reminder
        was fired.
        """
        if now is None:
            now = datetime.now()  # noqa: DTZ005

        due = pop_due(self._path, now)
        if not due:
            return

        for index, reminder in enumerate(due):
            body = (
                f"{reminder.title}: {reminder.message}"
                if reminder.message
                else reminder.title
            )
            if index == 0:
                self._tray.notify(_TRAY_TITLE, body)
            else:
                QTimer.singleShot(
                    index * _STAGGER_MS,
                    lambda b=body: self._tray.notify(_TRAY_TITLE, b),
                )

        self.changed.emit()

    def add(self, due: datetime, message: str, task: str, title: str) -> Reminder:
        """Persists a reminder and emits `changed`."""
        reminder = add(self._path, due, message, task, title)
        self.changed.emit()
        return reminder

    def remove(self, reminder_id: str) -> bool:
        """Persists the removal and emits `changed` when the reminder existed."""
        removed = remove(self._path, reminder_id)
        if removed:
            self.changed.emit()
        return removed

    def reminders(self) -> list[Reminder]:
        """Returns every reminder."""
        return load(self._path)

    def for_task(self, task: str) -> list[Reminder]:
        """Returns the reminders of one task folder name."""
        return for_task(load(self._path), task)
