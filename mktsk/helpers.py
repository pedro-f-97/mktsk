import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}

_TITLE_WORD = re.compile(r"[A-Z]?[a-z]*|\d+")

# the characters Windows refuses in a name, whatever the platform we run on
_WINDOWS_FORBIDDEN = frozenset('<>:"/\\|?*')

def is_reserved_name(name: str) -> bool:
    """Checks if the given name is reserved by Windows.

    The name is checked without its extension, because Windows reserves `CON`
    in `CON.txt` just as it does in a folder called `CON`.

    Args:
        name: Name to be checked.

    Returns:
        True if the name is a Windows reserved name.
    """
    return PureWindowsPath(name).stem.upper() in WINDOWS_RESERVED_NAMES

class TaskError(Exception):
    """Error raised when a task domain rule is violated."""

def validate_name(name: str) -> None:
    """Validates that the given name is usable on every platform.

    The rules are Windows', because it is the strictest of the two systems the
    project runs on: a name it accepts is accepted everywhere, and one it refuses
    is refused here rather than leaving a folder behind that cannot be opened.
    The component check uses `PureWindowsPath` rather than `Path`, which follows
    the platform we are on; the forbidden characters carry the same names anyway,
    so this is belt and braces rather than the rule doing the work.

    Args:
        name: Name to be validated.

    Raises:
        TaskError: If the name is empty or only spaces, carries a character
            Windows does not allow, is not a single path component, or ends in
            a dot or a space, which Windows drops rather than keeps.
    """
    if not name.strip():
        raise TaskError("Name must not be empty")

    # the component check comes next, so a name that is a path says so rather
    # than naming the separator as just another forbidden character
    if PureWindowsPath(name).name != name:
        raise TaskError(f"Name must be a single path component, got: {name!r}")

    if any(char in _WINDOWS_FORBIDDEN for char in name):
        raise TaskError(f"'{name}' has a character Windows does not allow in a name")

    if any(ord(char) < 32 for char in name):
        raise TaskError(f"'{name}' has a character Windows does not allow in a name")

    if name != name.rstrip(" ."):
        raise TaskError(f"'{name}' ends in a dot or a space, which Windows drops")

def readable_title(title: str) -> str:
    """Separates the words of a standardized title with spaces.

    `standardize_string` joins the words of a title in CamelCase, so an
    uppercase letter marks where a word begins. A digit marks one too, and
    consecutive digits stay together, so a title made only of digits keeps its
    value.

    Args:
        title: the standardized title to read.

    Returns:
        The title with its words separated by spaces.
    """
    return " ".join(word for word in _TITLE_WORD.findall(title) if word)


def open_file(file: Path) -> None:
    """Opens a file or folder with the operating system's default application.

    Args:
        file: File or folder to open.

    Raises:
        OSError: If the file cannot be opened.
    """
    try:
        if sys.platform == "win32":
            os.startfile(file)
        elif shutil.which("xdg-open"):
            subprocess.run(["xdg-open", file], check=True)
        else:
            subprocess.run(["gio", "open", file], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise OSError(f"Could not open: {file}") from error
