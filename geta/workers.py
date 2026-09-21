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

def create_folder(location: Path, name: str, date_prefix: str | None) -> Path:
    """Creates a folder with the given name at the given location.

    Args:
        location: path where the folder will be created
        name: name to give the folder
        date_prefix: optional date prefix in string format

    Returns:
        the path of the created folder or None if failed
    """
    if not date_prefix:
        date_prefix = datetime.datetime.now().strftime("%y%m%d")
    standardized_name = standardize_string(name)
    final_name = f"{date_prefix} - {standardized_name}" 
    folder_to_create = location / final_name

    try:
        folder_to_create.mkdir(parents=True, exist_ok=True)

    except OSError as error:
        raise Exception("Failed to create folder")
    
    return folder_to_create