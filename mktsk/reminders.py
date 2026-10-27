"""The reminders store: a JSON file of reminders due at a given time.

No Qt here: this is plain domain logic the GUI builds on.
"""

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config

_REMINDERS_NAME = "reminders.json"
_BAD_SUFFIX = ".bad"
_DUE_FORMAT = "%Y-%m-%dT%H:%M"


@dataclass(frozen=True)
class Reminder:
    """A reminder due at a given local time.

    Attributes:
        id: stable identifier, `uuid4().hex`.
        due: naive local time, minute precision.
        message: the reminder body, may be empty.
        task: the task folder name (`YYMMDD - TaskName`), never an absolute path.
        title: readable task title snapshot, used when the task can no longer be found.
    """

    id: str
    due: datetime
    message: str
    task: str
    title: str


def reminders_path() -> Path:
    """Where `reminders.json` lives: next to the shared config file."""
    return config.config_path().parent / _REMINDERS_NAME


def load(path: Path) -> list[Reminder]:
    """Loads the reminders from `path`, sorted by due.

    A missing file gives `[]`. An unreadable or corrupted file is renamed to
    `reminders.json.bad` (replacing an existing `.bad`) and gives `[]`. An
    invalid entry (missing key, bad date) is skipped and the valid ones kept.
    """
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        _rename_bad(path)
        return []

    if not isinstance(data, dict) or not isinstance(data.get("reminders"), list):
        _rename_bad(path)
        return []

    reminders: list[Reminder] = []
    for entry in data["reminders"]:
        reminder = _entry_to_reminder(entry)
        if reminder is not None:
            reminders.append(reminder)

    reminders.sort(key=lambda reminder: reminder.due)
    return reminders


def _entry_to_reminder(entry) -> Reminder | None:
    if not isinstance(entry, dict):
        return None
    try:
        due = datetime.strptime(entry["due"], _DUE_FORMAT)  # noqa: DTZ007
        return Reminder(
            id=entry["id"],
            due=due,
            message=entry.get("message", ""),
            task=entry["task"],
            title=entry["title"],
        )
    except (KeyError, TypeError, ValueError):
        return None


def _rename_bad(path: Path) -> None:
    bad = path.parent / (path.name + _BAD_SUFFIX)
    path.replace(bad)


def add(path: Path, due: datetime, message: str, task: str, title: str) -> Reminder:
    """Adds a reminder and returns it, creating the parent directory."""
    reminder = Reminder(
        id=uuid.uuid4().hex,
        due=due,
        message=message,
        task=task,
        title=title,
    )
    reminders = load(path)
    reminders.append(reminder)
    _write(path, reminders)
    return reminder


def remove(path: Path, reminder_id: str) -> bool:
    """Removes the reminder with `reminder_id`, answering whether it existed."""
    reminders = load(path)
    remaining = [reminder for reminder in reminders if reminder.id != reminder_id]
    if len(remaining) == len(reminders):
        return False
    _write(path, remaining)
    return True


def for_task(reminders: list[Reminder], task: str) -> list[Reminder]:
    """Returns the reminders whose task folder name is `task`."""
    return [reminder for reminder in reminders if reminder.task == task]


def pop_due(path: Path, now: datetime) -> list[Reminder]:
    """Returns the reminders due at or before `now`, sorted by due.

    Removes them from the file before returning, so each fires at most once.
    Reminders not yet due are left in place.
    """
    reminders = load(path)
    due = [reminder for reminder in reminders if reminder.due <= now]
    due.sort(key=lambda reminder: reminder.due)
    remaining = [reminder for reminder in reminders if reminder.due > now]
    if due:
        _write(path, remaining)
    return due


def _write(path: Path, reminders: list[Reminder]) -> None:
    """Atomically writes `reminders` to `path`, leaving no temp file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "reminders": [
            {
                "id": reminder.id,
                "due": reminder.due.strftime(_DUE_FORMAT),
                "message": reminder.message,
                "task": reminder.task,
                "title": reminder.title,
            }
            for reminder in reminders
        ],
    }
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
