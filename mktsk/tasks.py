import datetime
from pathlib import Path
from typing import NamedTuple

from . import files, helpers, listing, standards, state


class TaskResult(NamedTuple):
    """Outcome of `open_or_create_task`."""

    file: Path
    message: str


def _state_note(file: Path, new_state: str) -> str:
    """Writes the event that records the state, and words it for the message.

    A state that cannot be written never stops the task from being opened:
    the visit is what matters, and the state can be set again later, so the
    failure reaches the message instead of the caller.

    Args:
        file: the .md file of the task.
        new_state: the state to record.

    Returns:
        " (state: <state>)" when the event was written, or
        " (state not recorded)" when writing it failed.
    """
    try:
        state.set_state(file, new_state)
    except OSError:
        return " (state not recorded)"

    return f" (state: {new_state})"


def _resume_task(folder: Path, title: str, date: datetime.date) -> TaskResult:
    """Prepares an existing task folder for a new visit.

    Args:
        folder: the task folder to resume.
        title: the standardized title.
        date: the date of the new visit.

    Returns:
        The .md file to open and a message describing what happened, ending
        with the state change when this visit records one.

    Raises:
        TaskError: If the .md is in the old format, which the migration has to
            convert first.
    """
    # the title is the one the folder carries rather than the one the lookup was
    # given: a folder renamed by hand keeps the capitals of its own name, and the
    # .md follows that name. `resume_task` can also be handed a folder that is
    # not a task folder, a copy by hand, and there the title given is the only
    # one there is.
    folder_title = standards.task_folder_title(folder.name) or title

    file = files.create_md_file(folder, folder_title)
    formatted = date.strftime(helpers.DATE_FORMAT)

    # the state this visit starts from is the one the file had before it is
    # dated: only a new date section counts as work, and it takes a task that
    # is not already in-progress to in-progress
    before = state.current_state(file.read_text(encoding="utf-8"))

    if files.append_date_section(file, date):
        note = _state_note(file, "in-progress") if before != "in-progress" else ""
        return TaskResult(file, f"Opened: {folder.name} (added # {formatted}){note}")

    return TaskResult(file, f"Opened: {folder.name} (# {formatted} already there)")


def open_or_create_task(location: Path, raw_title: str) -> TaskResult:
    """Finds the task for a title, or creates it, and returns its .md file.

    An existing task is looked up by title on any date, inside `location`, and a
    new dated section is added to it. The title is unique within `location`, so
    the lookup is unambiguous there; should a directory hold two anyway, the most
    recent is the one resumed. With no match, a new task folder is created in
    `location`.

    Args:
        location: the directory the task belongs to.
        raw_title: the task title, as typed by the user.

    Returns:
        The .md file to open and a message describing what happened, ending
        with the state change when this visit records one.

    Raises:
        TaskError: If the title is empty, normalizes to nothing, or is a
            reserved Windows name.
    """
    title = standards.standardize_string(raw_title)

    if not title.strip():
        raise helpers.TaskError("invalid task description")

    if helpers.is_reserved_name(title):
        raise helpers.TaskError(f"'{title}' is a reserved name")

    today = datetime.datetime.now().astimezone().date()
    existing = listing.find_task_folder(location, title)

    if existing is not None:
        return _resume_task(existing, title, today)

    folder_name = standards.build_folder_name(title)
    created_folder = files.create_folder(location, folder_name)
    created_file = files.create_md_file(created_folder, title)

    # the file is born with the first section, the one that dates this visit
    files.append_date_section(created_file, today)

    # a task that comes into being is open, and the heading of the new
    # section is followed by two blank lines before the block, so a note
    # typed on the first one never runs into the events
    note = _state_note(created_file, "open")

    return TaskResult(created_file, f"Created: {folder_name}{note}")


def resume_task(folder: Path, title: str) -> TaskResult:
    """Adds a dated section to a task folder and returns its .md file.

    Unlike `open_or_create_task`, which looks a title up in the current
    directory, this resumes the folder it is given, wherever that folder lives.

    Args:
        folder: the task folder to resume.
        title: the standardized title of the task.

    Returns:
        The .md file to open and a message describing what happened, ending
        with the state change when this visit records one.
    """
    today = datetime.datetime.now().astimezone().date()

    return _resume_task(folder, title, today)


def rename_task(folder: Path, title: str, raw_title: str) -> TaskResult:
    """Renames a task folder and its .md file, keeping the date of the task.

    The date prefix stays put, so a renamed task keeps its place in the history.
    Only the names move: the title of a task lives in them, and the .md carries
    no heading naming it. The content is never read and never written, and
    renaming to the title the task already has does nothing.

    A step that fails is undone, in reverse, so the task is never left holding a
    .md whose name disagrees with the folder it sits in.

    Args:
        folder: the task folder to rename.
        title: the standardized title the task has now.
        raw_title: the new title, as typed by the user.

    Returns:
        The renamed .md file and a message describing what happened.

    Raises:
        TaskError: If the new title is empty, normalizes to nothing, is a
            reserved Windows name, or names a task that is already there.
        OSError: If the folder or the file cannot be renamed.
    """
    new_title = standards.standardize_string(raw_title)

    if not new_title.strip():
        raise helpers.TaskError("invalid task description")

    if helpers.is_reserved_name(new_title):
        raise helpers.TaskError(f"'{new_title}' is a reserved name")

    file = folder / f"{title}.md"

    if not file.is_file():
        raise helpers.TaskError(f"'{title}' has no Markdown file")

    if new_title == title:
        return TaskResult(file, f"Renamed: {folder.name}")

    date_prefix = folder.name.partition(standards._TASK_NAME_SEPARATOR)[0]
    renamed_folder = folder.parent / standards.build_folder_name(new_title, date_prefix)

    # the lookup ignores the date on purpose: a title is unique in a directory,
    # so one held by a task of any date is a clash. Keeping the title unique is
    # what leaves a later lookup by title unambiguous. The lookup ignores the
    # case, so the task being renamed is left out of it, or a rename that only
    # changes the case would be a clash with the task it already is.
    if listing.find_task_folder(folder.parent, new_title, exclude=folder) is not None:
        raise helpers.TaskError(f"'{new_title}' is already a task here")

    new_file = folder / f"{new_title}.md"

    # the file moves inside the folder first, or its old path stops resolving
    file.rename(new_file)

    try:
        folder.rename(renamed_folder)
    except OSError:
        # the folder did not move, so the file goes back to the name it had
        new_file.rename(file)
        raise

    renamed_file = renamed_folder / f"{new_title}.md"

    return TaskResult(renamed_file, f"Renamed: {renamed_folder.name}")
