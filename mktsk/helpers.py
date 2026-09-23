import os
import subprocess
import sys
from pathlib import Path


def validate_name(name: str) -> None:
    """Validates that the given name is a single path component.

    Args:
        name: Name to be validated.

    Raises:
        ValueError: If the name contains path separators or is otherwise
            not a single path component.
    """
    if Path(name).name != name:
        raise ValueError(f"Name must be a single path component, got: {name!r}")

def open_file(file: Path) -> None:
    """Opens a file with the operating system's default application.

    Args:
        file: File to open.

    Raises:
        OSError: If the file cannot be opened.
    """
    try:
        if sys.platform == "win32":
            os.startfile(file)
        else:
            subprocess.run(["xdg-open", file], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise OSError(f"Could not open file: {file}") from error