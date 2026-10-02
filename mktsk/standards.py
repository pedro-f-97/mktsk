import datetime
import re  #regular expression operations
import unicodedata

from . import helpers

_TASK_NAME_SEPARATOR = " - "
_TASK_DATE_PREFIX_LENGTH = 6
_TASK_DATE_FORMAT = "%y%m%d"


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
