import datetime
from pathlib import Path

from . import helpers, parsing, standards, state

# the command that converts a tree of tasks to the format mktsk writes
_MIGRATION_COMMAND = "python -m mktsk.migration"


def _has_bom(content: str) -> bool:
    """Tells whether the text of a .md starts with a byte order mark."""
    return content.startswith(parsing.BOM)


def create_folder(location: Path, name: str) -> Path:
    """Creates a folder with the given name at the given location.

    The name is taken as it is given, so a name Windows reserves is only
    refused by the caller that knows it is a title. A task folder carries a
    date prefix, which `261001 - CON` shows is enough to keep the name out of
    the reserved set, so nothing is lost by leaving the check out here.

    Args:
        location: path where the folder will be created
        name: name to give the folder

    Returns:
        the path of the created folder

    Raises:
        TaskError: If the name is not a single path component, or carries a
            character, or ends in a way, that Windows does not accept.
    """
    helpers.validate_name(name)

    folder_to_create = location / name

    folder_to_create.mkdir(parents=True, exist_ok=True)

    return folder_to_create


def create_md_file(location: Path, name: str) -> Path:
    """Creates an .md file with the given name at the given location

    Args:
        location: path where the file will be created
        name: name to give the file

    Returns:
        the path of the created .md file

    Raises:
        TaskError: If the name is a single path component Windows accepts, or
            is a reserved name, which `CON.md` is as much as `CON` is.
    """
    helpers.validate_name(name)

    if helpers.is_reserved_name(name):
        raise helpers.TaskError(f"'{name}' is a reserved name")

    file_to_create = location / f"{name}.md"
    file_to_create.touch()

    return file_to_create


def append_date_section(file: Path, date: datetime.date) -> bool:
    """Adds a first level heading with the given date to the given .md file.

    The date of a visit is a level 1 heading, because the title of the task is
    the name of the folder and of the file rather than something inside it. The
    first section is the one a file is born with, and every visit after it is
    appended at the end.

    The final block of state events is the end of the file, so a new section is
    written in front of it and the block never moves from there. The heading of
    a new section is followed by two blank lines when a block is there, so a
    note typed on the first blank line is never glued to the events; without a
    block it is followed by the usual one.

    Existing content is never rewritten, only trailing whitespace is dropped, and
    a date that already has a section is not added twice. Whether it has one is
    read with `parse_task`, so a date written in another of the accepted forms,
    with stray spacing or inside a code block, counts the way it reads.

    A file in the old format is refused rather than read as the new one, so its
    title is never mistaken for an intervention. Nothing is written in that case.

    Args:
        file: file to append to.
        date: date of the new section.

    Returns:
        True if the section was added, False if the date was already there.

    Raises:
        TaskError: If the file is in the old format.
    """
    formatted = date.strftime(helpers.DATE_FORMAT)
    content = file.read_text(encoding="utf-8")

    if parsing.is_legacy(content):
        raise helpers.TaskError(
            f"'{file.name}' is in the old format: run "
            f"'{_MIGRATION_COMMAND} <folder>' to convert it"
        )

    if any(
        intervention.date == date
        for intervention in parsing.parse_task(content).interventions
    ):
        return False

    # a file keeps the mark it was written with, and the block of state events
    # stays at the end, so the new section goes in front of it
    bom = parsing.BOM if _has_bom(content) else ""
    prefix, event_block = state._split_event_block(parsing.without_bom(content))
    body = prefix.rstrip()

    # two blank lines follow the heading when a block is there, so a note typed
    # on the first blank line never runs into the events
    spacing = "\n\n" if event_block else "\n"

    # a file with nothing in it is born with the section and a blank line, so
    # the body can be typed straight away
    if not body:
        file.write_text(f"{bom}# {formatted}\n{spacing}{event_block}", encoding="utf-8")
    else:
        file.write_text(
            f"{bom}{body}\n\n# {formatted}\n{spacing}{event_block}", encoding="utf-8"
        )

    return True


def create_category(location: Path, raw_name: str) -> Path:
    """Creates a new category folder in the given directory.

    A category is a plain subdirectory, so it is not a task folder and does not
    follow the task naming rules. The name is stripped of accents, so that the
    folder stays ASCII, but otherwise it is left as the user typed it. A name
    that is already there does not produce an error: the existing path is
    returned instead.

    Args:
        location: the directory to create the category in.
        raw_name: the name to give the category, as typed by the user.

    Returns:
        The path of the category folder.

    Raises:
        TaskError: If the name is empty, contains path separators, is a
            reserved Windows name, would be hidden, or looks like a task folder.
    """
    name = standards._without_accents(raw_name)

    # a folder name is ASCII, and there is no accent to fold a Japanese word
    if not name.strip() or not name.isascii():
        raise helpers.TaskError("invalid category name")

    helpers.validate_name(name)

    if helpers.is_reserved_name(name):
        raise helpers.TaskError(f"'{name}' is a reserved name")

    if name.startswith("."):
        raise helpers.TaskError("invalid category name")

    if standards.is_task_folder(name) or standards._reserved_task_title(name):
        raise helpers.TaskError("invalid category name")

    category = location / name

    # exist_ok, so a name that is already there is not an error
    category.mkdir(exist_ok=True)

    return category
