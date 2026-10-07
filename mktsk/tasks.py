import datetime
import os
import shutil
import zipfile
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


def _archive_members(folder: Path, md: Path) -> list[tuple[str, bytes]]:
    """Reads every file of a folder into the members of its archive.

    The .md is the one member read as text: it goes in carrying the closed
    event, while the file on disk keeps whatever it had, so a failure halfway
    never leaves the task half closed. Every other file is archived as it is.

    Args:
        folder: the task folder to archive.
        md: the .md of the task, the member that carries the closed event.

    Returns:
        The archive path of each file of the folder and its content, in the
        order the files come out of the folder.
    """
    members = []

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue

        arcname = f"{folder.name}/{path.relative_to(folder).as_posix()}"

        if path == md:
            content = path.read_text(encoding="utf-8")
            # the event line carries no zone, so the wall clock of the machine
            # is enough and the time is kept naive, the way set_state writes it
            now = datetime.datetime.now()  # noqa: DTZ005
            closed = state.with_state(content, "closed", now)
            members.append((arcname, closed.encode("utf-8")))
        else:
            members.append((arcname, path.read_bytes()))

    return members


def _verify_archive(temp: Path, members: list[tuple[str, bytes]]) -> None:
    """Reopens the archive just written and checks it against what went in.

    Nothing is renamed and no folder is removed until this passes, so an
    archive that lost a member or came out short never reaches the name a
    closed task answers to.

    Args:
        temp: the archive under its temporary name.
        members: the archive paths and contents that were written.

    Raises:
        TaskError: If the archive is corrupt, holds other names than the ones
            written, or a member has the wrong size.
    """
    expected_sizes = {name: len(data) for name, data in members}

    with zipfile.ZipFile(temp) as archive:
        corrupt = archive.testzip()

        if corrupt is not None:
            raise helpers.TaskError(
                f"archive verification failed: '{corrupt}' is corrupt"
            )

        names = archive.namelist()

        if len(names) != len(expected_sizes) or set(names) != set(expected_sizes):
            raise helpers.TaskError("archive verification failed: unexpected contents")

        for info in archive.infolist():
            if info.file_size != expected_sizes[info.filename]:
                raise helpers.TaskError(
                    f"archive verification failed: '{info.filename}' has the wrong size"
                )


def close_task(folder: Path, title: str) -> TaskResult:
    """Compresses a task folder into an archive beside it and deletes it.

    The archive takes the place of the folder in the same directory, named
    after it, and its .md carries the closed event while the .md on disk is
    left as it is. Nothing is deleted until the archive exists, opens and
    matches what went into it, so a failure at any point loses nothing: a
    failure before the folder goes leaves the folder alone, and a failure
    removing it keeps the archive and the folder both.

    Args:
        folder: the task folder to close.
        title: the standardized title of the task.

    Returns:
        The archive and a message describing what happened.

    Raises:
        TaskError: If the task is already archived, has no .md, the archive
            fails verification, or the folder cannot be removed now that the
            archive is in place.
    """
    archive = folder.parent / f"{folder.name}.zip"

    if listing.find_task_archive(folder.parent, title) is not None:
        raise helpers.TaskError(f"'{title}' is already archived")

    file = folder / f"{title}.md"

    if not file.is_file():
        raise helpers.TaskError(f"'{title}' has no Markdown file")

    temp = folder.parent / f".{folder.name}.zip.part"

    try:
        members = _archive_members(folder, file)

        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as handle:
            for name, data in members:
                handle.writestr(name, data)

        _verify_archive(temp, members)
        os.replace(temp, archive)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

    try:
        shutil.rmtree(folder)
    except OSError as error:
        raise helpers.TaskError(
            f"'{folder.name}' is archived as {archive.name}, but the folder "
            f"could not be removed: {error}"
        ) from error

    return TaskResult(archive, f"Closed: {archive.name}")
