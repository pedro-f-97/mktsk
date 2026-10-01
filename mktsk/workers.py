import datetime
import re  #regular expression operations
import unicodedata
from pathlib import Path
from typing import NamedTuple

from . import helpers

DATE_FORMAT = "%d/%m/%Y"

_TASK_NAME_SEPARATOR = " - "
_TASK_DATE_PREFIX_LENGTH = 6
_TASK_DATE_FORMAT = "%y%m%d"


class TaskResult(NamedTuple):
    """Outcome of `open_or_create_task`."""

    file: Path
    message: str


class TaskEntry(NamedTuple):
    """A task folder found under a base directory."""

    date: datetime.date
    title: str
    file: Path


class TaskGroup(NamedTuple):
    """Tasks found in the base directory or in one of its subdirectories."""

    category: Path | None
    entries: list[TaskEntry]


def _without_accents(value: str) -> str:
    """Removes the accents of a string, leaving everything else as it is.

    Args:
        value: the string to strip.

    Returns:
        The string without its combining marks.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))

def standardize_string(string_: str) -> str:
    """Normalize a string by removing accents, special characters and spacing.

    Args:
        string_: The target string to be standardized.

    Returns:
        The standardized string.
    """
    # remove special characters
    without_accents = _without_accents(string_)

    # an apostrophe joins a word rather than cutting it in two, so a
    # contraction is one word: "It's" standardizes to "Its"
    joined = without_accents.replace("\u2019", "").replace("'", "")

    # remove spacing
    words = re.split(r"[^A-Za-z0-9]+", joined)
    
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
    date = datetime.datetime.now().astimezone().strftime(DATE_FORMAT)

    # a heading that already names the task, or nothing to insert one before
    if _retitled(content, title, title) is None:
        body = content.lstrip()

        if body:
            file.write_text(f"# {title}\n\n{body}", encoding="utf-8")
            return False

        file.write_text(f"# {title}\n\n## {date}\n\n", encoding="utf-8")
        return True

    return False

def is_task_folder(name: str) -> bool:
    """Tells whether a directory name is a task folder.

    A task folder is named `<yymmdd> - <StandardizedTitle>`. The date prefix must
    be a real calendar date, and the title must be ASCII alphanumeric and must
    not start lowercase, which is exactly what `standardize_string` produces.

    The title must not be a name Windows reserves either. The date prefix keeps
    `261001 - CON` out of the reserved set as a folder name, but the .md inside
    it would be `CON.md`, which is reserved, so a task the shape check accepts
    would still be one that cannot be opened.

    Args:
        name: the directory name to check.

    Returns:
        True if the name identifies a task folder.
    """
    date_prefix, separator, title = name.partition(_TASK_NAME_SEPARATOR)

    if not separator or not title:
        return False

    if len(date_prefix) != _TASK_DATE_PREFIX_LENGTH or not date_prefix.isdigit():
        return False

    try:
        # only the calendar date matters here, no timezone arithmetic to do
        datetime.datetime.strptime(date_prefix, _TASK_DATE_FORMAT)  # noqa: DTZ007
    except ValueError:
        return False

    return (
        title.isascii()
        and title.isalnum()
        and not title[0].islower()
        and not helpers.is_reserved_name(title)
    )

def _reserved_task_title(name: str) -> bool:
    """Tells whether a task folder name carries a title Windows reserves.

    The date prefix keeps the folder name itself out of the reserved set, so it
    is the title that has to be checked, which is also what its .md is called.
    Only the shape of the name is read here, and not the calendar date or the
    standardization of the title, because `is_task_folder` decides on both of
    those and refuses the name as a task; this says why, so a category cannot
    take the name that a task folder would have had.

    Args:
        name: the directory name to check.

    Returns:
        True when the name looks like a task folder whose title is reserved.
    """
    date_prefix, separator, title = name.partition(_TASK_NAME_SEPARATOR)

    return (
        bool(separator)
        and len(date_prefix) == _TASK_DATE_PREFIX_LENGTH
        and date_prefix.isdigit()
        and helpers.is_reserved_name(title)
    )

def find_task_folder(location: Path, title: str) -> Path | None:
    """Finds the task folder for a title in the given directory, on any date.

    The title of a task is unique within its directory, which is what makes a
    lookup unambiguous there. The date is ignored, so `260918 - Foo` is still
    the task `mktsk Foo` resumes months later. A task of the same title in
    another directory is a different task and is not considered.

    Should a directory hold more than one anyway, because a folder was copied
    by hand or restored from a backup, the most recent one wins rather than
    whichever came first out of `iterdir`.

    Args:
        location: the directory to look in.
        title: the standardized title to look for.

    Returns:
        The task folder, or None if the directory holds none.
    """
    if not location.is_dir():
        return None

    matches = []

    for entry in location.iterdir():
        if not entry.is_dir():
            continue

        parts = _task_date_and_title(entry.name)

        if parts is not None and parts[1] == title:
            matches.append((parts[0], entry))

    if not matches:
        return None

    # a folder copied in by hand leaves the date, so the newest wins
    return max(matches, key=lambda match: match[0])[1]

def _task_date_and_title(name: str) -> tuple[datetime.date, str] | None:
    """Splits a task folder name into its date and its standardized title.

    Args:
        name: the directory name to split.

    Returns:
        The date and the title, or None if the name is not a task folder.
    """
    if not is_task_folder(name):
        return None

    date_prefix, _separator, title = name.partition(_TASK_NAME_SEPARATOR)

    # is_task_folder already parsed the prefix as a real date, so this cannot fail
    parsed = datetime.datetime.strptime(date_prefix, _TASK_DATE_FORMAT)  # noqa: DTZ007

    return parsed.date(), title

def task_folder_title(name: str) -> str | None:
    """Returns the standardized title a task folder name carries.

    Args:
        name: the directory name to read.

    Returns:
        The standardized title, or None if the name is not a task folder.
    """
    parts = _task_date_and_title(name)

    return None if parts is None else parts[1]

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

        parts = _task_date_and_title(folder.name)
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
            and not is_task_folder(entry.name)
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

    # signing a file with nothing in it dates it, so there is no visit to add
    if sign_md_file(file, title):
        return TaskResult(file, f"Opened: {folder.name}")

    formatted = date.strftime(DATE_FORMAT)

    if append_date_section(file, date):
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
    new_title = standardize_string(raw_title)

    if not new_title.strip():
        raise helpers.TaskError("invalid task description")

    if helpers.is_reserved_name(new_title):
        raise helpers.TaskError(f"'{new_title}' is a reserved name")

    file = folder / f"{title}.md"

    if not file.is_file():
        raise helpers.TaskError(f"'{title}' has no Markdown file")

    if new_title == title:
        return TaskResult(file, f"Renamed: {folder.name}")

    date_prefix = folder.name.partition(_TASK_NAME_SEPARATOR)[0]
    renamed_folder = folder.parent / build_folder_name(new_title, date_prefix)

    # the lookup ignores the date on purpose: a title is unique in a directory,
    # so one held by a task of any date is a clash. Keeping the title unique is
    # what leaves a later lookup by title unambiguous
    if find_task_folder(folder.parent, new_title) is not None:
        raise helpers.TaskError(f"'{new_title}' is already a task here")

    # read before anything moves, so a step that fails later can put the file back
    content = file.read_text(encoding="utf-8")
    retitled = _retitled(content, title, new_title)

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
    name = _without_accents(raw_name)

    # a folder name is ASCII, and there is no accent to fold a Japanese word
    if not name.strip() or not name.isascii():
        raise helpers.TaskError("invalid category name")

    helpers.validate_name(name)

    if helpers.is_reserved_name(name):
        raise helpers.TaskError(f"'{name}' is a reserved name")

    if name.startswith("."):
        raise helpers.TaskError("invalid category name")

    if is_task_folder(name) or _reserved_task_title(name):
        raise helpers.TaskError("invalid category name")

    category = location / name

    # exist_ok, so a name that is already there is not an error
    category.mkdir(exist_ok=True)

    return category
