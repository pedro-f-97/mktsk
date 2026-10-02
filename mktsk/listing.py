import datetime
from pathlib import Path
from typing import NamedTuple

from . import standards


class TaskEntry(NamedTuple):
    """A task folder found under a base directory."""

    date: datetime.date
    title: str
    file: Path


class TaskGroup(NamedTuple):
    """Tasks found in the base directory or in one of its subdirectories."""

    category: Path | None
    entries: list[TaskEntry]


def find_task_folder(
    location: Path, title: str, exclude: Path | None = None
) -> Path | None:
    """Finds the task folder for a title in the given directory, on any date.

    The title of a task is unique within its directory, which is what makes a
    lookup unambiguous there. The date is ignored, so `260918 - Foo` is still
    the task `mktsk Foo` resumes months later. A task of the same title in
    another directory is a different task and is not considered.

    The comparison ignores the case, because `standardize_string` lowers the
    capitals inside a title and a folder renamed by hand keeps them, so anyone
    copying a folder name into the terminal has to reach the task it names
    rather than a second one.

    Should a directory hold more than one anyway, because a folder was copied
    by hand or restored from a backup, the most recent one wins rather than
    whichever came first out of `iterdir`.

    Args:
        location: the directory to look in.
        title: the standardized title to look for.
        exclude: a folder to leave out of the search, which is how `rename_task`
            keeps a task from clashing with itself when only the case changes.

    Returns:
        The task folder, or None if the directory holds none.
    """
    if not location.is_dir():
        return None

    matches = []

    for entry in location.iterdir():
        if exclude is not None and entry == exclude:
            continue

        if not entry.is_dir():
            continue

        parts = standards._task_date_and_title(entry.name)

        if parts is not None and parts[1].casefold() == title.casefold():
            matches.append((parts[0], entry))

    if not matches:
        return None

    # a folder copied in by hand leaves the date, so the newest wins
    return max(matches, key=lambda match: match[0])[1]


def _tasks_in(directory: Path) -> list[TaskEntry]:
    """Collects the task folders of a directory, newest first.

    A task folder is listed only when it holds the .md file that goes with it,
    so a folder left without one is never offered to open. A directory that
    cannot be read holds no tasks, and is left out rather than raising.

    Args:
        directory: the directory to look in.

    Returns:
        One entry per task folder, newest first and alphabetical for tasks of
        the same date.
    """
    try:
        folders = list(directory.iterdir())
    except OSError:
        return []

    entries = []

    for folder in folders:
        if not folder.is_dir():
            continue

        parts = standards._task_date_and_title(folder.name)
        if parts is None:
            continue

        date, title = parts
        file = folder / f"{title}.md"
        if file.is_file():
            entries.append(TaskEntry(date, title, file))

    return sorted(entries, key=lambda entry: (-entry.date.toordinal(), entry.title))


def list_subdirectories(location: Path) -> list[Path]:
    """Lists the immediate subdirectories that are not task folders.

    Hidden directories are left out, so a listing does not walk into `.git` and
    friends. The list stays one level deep, so a subdirectory of a
    subdirectory is never a category. A directory that cannot be read holds no
    subdirectories, and is left out rather than raising, which is what
    `_tasks_in` does with the same problem.

    Args:
        location: the directory to look in.

    Returns:
        The subdirectories, in alphabetical order, or nothing when the
        directory cannot be read.
    """
    try:
        entries = list(location.iterdir())
    except OSError:
        return []

    return sorted(
        (
            entry
            for entry in entries
            if entry.is_dir()
            and not entry.name.startswith(".")
            and not standards.is_task_folder(entry.name)
        ),
        key=lambda path: path.name.lower(),
    )


def find_task_groups(location: Path) -> list[TaskGroup]:
    """Finds the tasks in a directory and in its immediate subdirectories.

    Every subdirectory that is not a task folder becomes a category named after
    it, so tasks kept apart in a subdirectory are still told apart in the list.
    The search stops one level down, so a task inside a subdirectory of a
    subdirectory is not found.

    Args:
        location: the directory to look in.

    Returns:
        The tasks of `location` first, with a category of None, then the tasks
        of each subdirectory in alphabetical order. Groups without tasks are
        left out.
    """
    if not location.is_dir():
        return []

    groups: list[TaskGroup] = []

    root_entries = _tasks_in(location)
    if root_entries:
        groups.append(TaskGroup(None, root_entries))

    for subdirectory in list_subdirectories(location):
        entries = _tasks_in(subdirectory)
        if entries:
            groups.append(TaskGroup(subdirectory, entries))

    return groups
