import datetime
import re  #regular expression operations
import unicodedata
from pathlib import Path


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
        date_prefix = datetime.datetime.now(tz=datetime.UTC).strftime("%y%m%d")

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
    file_to_create = location / f"{name}.md"
    file_to_create.touch()

    return file_to_create

def sign_md_file(file: Path, folder: Path) -> None:
    """Writes given folder's name in the first line of the given .md file

    Args:
        file: file to be signed
        folder: folder to use for signing
    """
    content = file.read_text(encoding="utf-8")
    lines = content.splitlines()

    if lines:
        if lines[0] == f"# {folder.name}":
            return

        raise ValueError("Markdown file already contains content.")

    file.write_text(f"# {folder.name}\n", encoding="utf-8")