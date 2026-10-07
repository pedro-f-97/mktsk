import datetime
from pathlib import Path
from typing import NamedTuple

from . import parsing, standards, state


class TaskEntry(NamedTuple):
    """A task folder found under a base directory.

    Attributes:
        date: the date in the name of the folder, the day the task was created.
        title: the standardized title of the task.
        file: the .md that goes with the folder.
        last_activity: the most recent intervention of the .md, or the folder date
            when the file carries none or cannot be read.
        interventions: how many interventions the .md carries.
        state: what the .md says the task is in, `open` when nothing can be
            read out of it.
    """

    date: datetime.date
    title: str
    file: Path
    last_activity: datetime.date
    interventions: int
    state: str


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


def _activity(file: Path, date: datetime.date) -> tuple[datetime.date, int, str]:
    """Reads the activity and the state of a task out of its .md.

    The date of the folder stands in for the last activity when the file is in
    the old format, when it carries no intervention, and when it cannot be read:
    a task is still a task when nothing can be read out of it, and one file that
    cannot be read never brings the listing down. An old file is not read as the
    new one, because the dated heading a conversion left behind is content of a
    file mktsk refuses to touch rather than a visit to the task. The state is
    `open` in those same cases, which is what a file with nothing in it is.

    Args:
        file: the .md of the task.
        date: the date in the name of the folder, as a last resort.

    Returns:
        The last activity of the task, how many interventions it carries, and
        the state its .md says it is in.
    """
    try:
        content = file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return date, 0, "open"

    if parsing.is_legacy(content):
        return date, 0, "open"

    parsed = parsing.parse_task(content)
    task_state = state.current_state(content)

    if parsed.last_activity is None:
        return date, 0, task_state

    return parsed.last_activity, len(parsed.interventions), task_state


def _tasks_in(directory: Path) -> list[TaskEntry]:
    """Collects the task folders of a directory, by last activity.

    A task folder is listed only when it holds the .md file that goes with it,
    so a folder left without one is never offered to open. A directory that
    cannot be read holds no tasks, and is left out rather than raising.

    Args:
        directory: the directory to look in.

    Returns:
        One entry per task folder, by last activity, newest first and
        alphabetical for tasks of the same last activity.
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
            last_activity, interventions, task_state = _activity(file, date)
            entries.append(
                TaskEntry(date, title, file, last_activity, interventions, task_state)
            )

    return sorted(
        entries,
        key=lambda entry: (-entry.last_activity.toordinal(), entry.title),
    )


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
