import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}

_TITLE_WORD = re.compile(r"[A-Z]?[a-z]*|\d+")

def is_reserved_name(name: str) -> bool:
    """Checks if the given name is reserved by Windows.

    Args:
        name: Name to be checked.

    Returns:
        True if the name is a Windows reserved name.
    """
    return name.upper() in WINDOWS_RESERVED_NAMES

class TaskError(Exception):
    """Error raised when a task domain rule is violated."""

def validate_name(name: str) -> None:
    """Validates that the given name is a single path component.

    Args:
        name: Name to be validated.

    Raises:
        TaskError: If the name contains path separators or is otherwise
            not a single path component.
    """
    if Path(name).name != name:
        raise TaskError(f"Name must be a single path component, got: {name!r}")

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
