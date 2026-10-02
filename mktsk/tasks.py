import datetime
from pathlib import Path
from typing import NamedTuple

from . import files, helpers, listing, standards


class TaskResult(NamedTuple):
    """Outcome of `open_or_create_task`."""

    file: Path
    message: str


def _resume_task(folder: Path, title: str, date: datetime.date) -> TaskResult:
    """Prepares an existing task folder for a new visit.

    Args:
        folder: the task folder to resume.
        title: the standardized title.
        date: the date of the new visit.

    Returns:
        The .md file to open and a message describing what happened.
    """
    # the title is the one the folder carries rather than the one the lookup was
    # given: a folder renamed by hand keeps the capitals of its own name, and the
    # .md and the heading inside it both follow that name. `resume_task` can also
    # be handed a folder that is not a task folder, a copy by hand, and there the
    # title given is the only one there is.
    folder_title = standards.task_folder_title(folder.name) or title

    file = files.create_md_file(folder, folder_title)

    # signing a file with nothing in it dates it, so there is no visit to add
    if files.sign_md_file(file, folder_title):
        return TaskResult(file, f"Opened: {folder.name}")

    formatted = date.strftime(helpers.DATE_FORMAT)

    if files.append_date_section(file, date):
        return TaskResult(file, f"Opened: {folder.name} (added ## {formatted})")

    return TaskResult(file, f"Opened: {folder.name} (## {formatted} already there)")


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
        The .md file to open and a message describing what happened.

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
    files.sign_md_file(created_file, title)

    return TaskResult(created_file, f"Created: {folder_name}")


def resume_task(folder: Path, title: str) -> TaskResult:
    """Adds a dated section to a task folder and returns its .md file.

    Unlike `open_or_create_task`, which looks a title up in the current
    directory, this resumes the folder it is given, wherever that folder lives.

    Args:
        folder: the task folder to resume.
        title: the standardized title of the task.

    Returns:
        The .md file to open and a message describing what happened.
    """
    today = datetime.datetime.now().astimezone().date()

    return _resume_task(folder, title, today)


def rename_task(folder: Path, title: str, raw_title: str) -> TaskResult:
    """Renames a task folder and its .md file, keeping the date of the task.

    The date prefix stays put, so a renamed task keeps its place in the history,
    and only the leading `#` heading is rewritten, and only when it matches the
    title the task had. Renaming to the title it already has does nothing.

    A step that fails is undone, in reverse, so the task is never left holding a
    file whose name and heading disagree with the folder it sits in.

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

    # read before anything moves, so a step that fails later can put the file back
    content = file.read_text(encoding="utf-8")
    retitled = files._retitled(content, title, new_title)

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

    if retitled is not None:
        try:
            renamed_file.write_text(retitled, encoding="utf-8")
        except OSError:
            # the heading could not be written, so the whole rename is undone
            # rather than left with a name and a heading that disagree
            renamed_file.write_text(content, encoding="utf-8")
            renamed_folder.rename(folder)
            new_file.rename(file)
            raise

    return TaskResult(renamed_file, f"Renamed: {renamed_folder.name}")
