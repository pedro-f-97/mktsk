import datetime
import re
from pathlib import Path

from . import helpers, standards


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


def sign_md_file(file: Path, title: str) -> bool:
    """Writes given title and the current date as headings in the given .md file.

    The title becomes the first level heading and the date, in `dd/mm/yyyy`
    format, the second level heading. A blank line follows, so the body can be
    typed straight away.

    A file whose leading heading already names the task is left untouched. A
    file carrying something else, which is content from a folder copied by hand
    or restored from a backup, gains the missing heading at the start and keeps
    everything below it as it was; nothing is ever rewritten or dropped, so the
    content of another task is never mistaken for the identity of this one.

    Args:
        file: file to be signed
        title: string to use as the heading, e.g. the standardized task title

    Returns:
        True when the file carried no dated section of its own and the date
        written here is the first, False when there was content to keep.
    """
    content = file.read_text(encoding="utf-8")
    date = datetime.datetime.now().astimezone().strftime(helpers.DATE_FORMAT)

    # a heading that already names the task, or nothing to insert one before
    if _retitled(content, title, title) is None:
        body = content.lstrip()

        if body:
            file.write_text(f"# {title}\n\n{body}", encoding="utf-8")
            return False

        file.write_text(f"# {title}\n\n## {date}\n\n", encoding="utf-8")
        return True

    return False


def append_date_section(file: Path, date: datetime.date) -> bool:
    """Adds a second level heading with the given date at the end of the .md file.

    Each visit to a task keeps its own dated section. Existing content is never
    rewritten, only trailing whitespace is dropped, and a section for a date
    that is already there is not added twice.

    Args:
        file: file to append to.
        date: date of the new section.

    Returns:
        True if the section was added, False if the date was already there.
    """
    formatted = date.strftime(helpers.DATE_FORMAT)

    content = file.read_text(encoding="utf-8")

    # the heading may carry stray spacing, as hand written ones do
    if re.search(rf"^##\s+{re.escape(formatted)}\s*$", content, re.MULTILINE):
        return False

    file.write_text(f"{content.rstrip()}\n\n## {formatted}\n\n", encoding="utf-8")

    return True


def _retitled(content: str, title: str, new_title: str) -> str | None:
    """Returns the content with its leading heading rewritten when it names the task.

    Only a first level heading that matches the title the file was created with
    is touched. Everything else, hand written text and dated sections alike, is
    left exactly as it was, and None says so, so the caller leaves the file alone
    rather than rewriting it with the same text.

    Args:
        content: the text of the .md file.
        title: the standardized title the heading is expected to carry.
        new_title: the standardized title to write in its place.

    Returns:
        The rewritten content, or None when there is no heading to rewrite.
    """
    heading = f"# {title}"

    lines = content.split("\n")

    for index, line in enumerate(lines):
        if not line.strip():
            continue

        if line.strip() == heading:
            lines[index] = f"# {new_title}"
            return "\n".join(lines)

        return None

    return None


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
