import datetime
import re  #regular expression operations
import unicodedata
from pathlib import Path
from typing import NamedTuple

from . import helpers

DATE_FORMAT = "%d/%m/%Y"

_TASK_NAME_SEPARATOR = " - "
_TASK_DATE_PREFIX_LENGTH = 6


class TaskResult(NamedTuple):
    """Outcome of `open_or_create_task`."""

    file: Path
    message: str


def standardize_string(string_: str) -> str:
    """Normalize a string by removing accents, special characters and spacing.

    Args:
        string_: The target string to be standardized.

    Returns:
        The standardized string.
    """
    # remove special characters
    decomposed = unicodedata.normalize("NFKD", string_)
    chars = []
    for c in decomposed:
        if not unicodedata.combining(c):
            chars.append(c)
    without_accents = "".join(chars)

    # remove spacing
    words = re.split(r"[^A-Za-z0-9]+", without_accents)
    
    # capitalize and join every word
    capitalized = []
    for word in words:
        if word:
            capitalized.append(word.capitalize())
    result = "".join(capitalized)

    return result

def build_folder_name(name: str, date_prefix: str | None = None) -> str:
    """Builds a folder name from a date prefix and a name.

    Args:
        name: Base name to be used.
        date_prefix: Optional date prefix. If not given, uses current
            date in `yymmdd` format.

    Returns:
        The formatted folder name.
    """
    if not date_prefix:
        date_prefix = datetime.datetime.now().astimezone().strftime("%y%m%d")

    name = f"{date_prefix} - {name}"
    return name

def create_folder(location: Path, name: str) -> Path:
    """Creates a folder with the given name at the given location.

    Args:
        location: path where the folder will be created
        name: name to give the folder

    Returns:
        the path of the created folder
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
    """
    helpers.validate_name(name)
    file_to_create = location / f"{name}.md"
    file_to_create.touch()

    return file_to_create

def sign_md_file(file: Path, title: str) -> None:
    """Writes given title and the current date as headings in the given .md file.

    The title becomes the first level heading and the date, in `dd/mm/yyyy`
    format, the second level heading. A blank line follows, so the body can be
    typed straight away.

    If the file already contains content, it is left untouched.

    Args:
        file: file to be signed
        title: string to use as the heading, e.g. the standardized task title
    """
    content = file.read_text(encoding="utf-8")

    if not content.strip():
        date = datetime.datetime.now().astimezone().strftime(DATE_FORMAT)
        file.write_text(f"# {title}\n\n## {date}\n\n", encoding="utf-8")

def find_task_folder(location: Path, title: str) -> Path | None:
    """Finds the task folder for a title in the given directory, on any date.

    A folder matches when its name is a six digit date prefix, `" - "` and the
    title. The search stays in `location`, so a task of the same name in another
    directory is a different task and is not considered.

    Args:
        location: the directory to look in.
        title: the standardized title to look for.

    Returns:
        The task folder, or None if the directory holds none.
    """
    if not location.is_dir():
        return None

    for entry in sorted(location.iterdir()):
        if not entry.is_dir():
            continue

        date_prefix, separator, folder_title = entry.name.partition(
            _TASK_NAME_SEPARATOR
        )

        if (
            separator
            and folder_title == title
            and len(date_prefix) == _TASK_DATE_PREFIX_LENGTH
            and date_prefix.isdigit()
        ):
            return entry

    return None

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
    formatted = date.strftime(DATE_FORMAT)

    content = file.read_text(encoding="utf-8")

    # the heading may carry stray spacing, as hand written ones do
    if re.search(rf"^##\s+{re.escape(formatted)}\s*$", content, re.MULTILINE):
        return False

    file.write_text(f"{content.rstrip()}\n\n## {formatted}\n\n", encoding="utf-8")

    return True

def _resume_task(folder: Path, title: str, date: datetime.date) -> TaskResult:
    """Prepares an existing task folder for a new visit.

    Args:
        folder: the task folder to resume.
        title: the standardized title.
        date: the date of the new visit.

    Returns:
        The .md file to open and a message describing what happened.
    """
    file = create_md_file(folder, title)

    if not file.read_text(encoding="utf-8").strip():
        sign_md_file(file, title)
        return TaskResult(file, f"Opened: {folder.name}")

    formatted = date.strftime(DATE_FORMAT)

    if append_date_section(file, date):
        return TaskResult(file, f"Opened: {folder.name} (added ## {formatted})")

    return TaskResult(file, f"Opened: {folder.name} (## {formatted} already there)")

def open_or_create_task(location: Path, raw_title: str) -> TaskResult:
    """Finds the task for a title, or creates it, and returns its .md file.

    An existing task is looked up by title on any date, inside `location`, and a
    new dated section is added to it. With no match, a new task folder is
    created in `location`.

    Args:
        location: the directory the task belongs to.
        raw_title: the task title, as typed by the user.

    Returns:
        The .md file to open and a message describing what happened.

    Raises:
        TaskError: If the title is empty, normalizes to nothing, or is a
            reserved Windows name.
    """
    title = standardize_string(raw_title)

    if not title.strip():
        raise helpers.TaskError("invalid task description")

    if helpers.is_reserved_name(title):
        raise helpers.TaskError(f"'{title}' is a reserved name")

    today = datetime.datetime.now().astimezone().date()
    existing = find_task_folder(location, title)

    if existing is not None:
        return _resume_task(existing, title, today)

    folder_name = build_folder_name(title)
    created_folder = create_folder(location, folder_name)
    created_file = create_md_file(created_folder, title)
    sign_md_file(created_file, title)

    return TaskResult(created_file, f"Created: {folder_name}")