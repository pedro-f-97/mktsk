import enum
import json
import os
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from . import helpers, standards

MAXIMUM_CATEGORIES = 2

_WINDOWS_FORBIDDEN = frozenset('<>:"/\\|?*')
_CONFIG_NAME = "config.json"
_APP_FOLDER = "mktsk"


class BaseFolderState(enum.Enum):
    """What the shared config says about the base folder."""

    OK = "ok"
    NOT_CONFIGURED = "not-configured"
    MISSING = "missing"


@dataclass(frozen=True)
class BaseFolder:
    """The result of resolving the base folder.

    Attributes:
        state: whether the saved folder is usable, absent or gone.
        path: the saved folder, when there is one to name.
    """

    state: BaseFolderState
    path: Path | None = None


def _home(environment: Mapping[str, str]) -> Path:
    """Returns the home folder the given environment names."""
    home = environment.get("HOME")
    return Path(home) if home else Path.home()


def config_path(
    env: Mapping[str, str] | None = None,
    platform: str = sys.platform,
) -> Path:
    """Returns where the shared config file lives on this platform.

    Args:
        env: the environment to read, the process environment when None.
        platform: the platform to decide for, the running one when None.

    Returns:
        The path of the config file.
    """
    environment = os.environ if env is None else env

    if platform.startswith("win"):
        appdata = environment.get("APPDATA")
        root = Path(appdata) if appdata else _home(environment) / "AppData" / "Roaming"
    elif platform == "darwin":
        root = _home(environment) / "Library" / "Application Support"
    else:
        configured = environment.get("XDG_CONFIG_HOME")
        root = Path(configured) if configured else _home(environment) / ".config"

    return root / _APP_FOLDER / _CONFIG_NAME


def load_config(config_file: Path | None = None) -> Path | None:
    """Reads the base folder saved in the config file.

    Nothing the file can hold is an error: a file that is missing, cannot be
    read, is not JSON, is not an object or carries no usable folder means the
    same thing, that no folder is saved.

    Args:
        config_file: the file to read, the platform default when None.

    Returns:
        The saved base folder, or None when there is none.
    """
    target = config_path() if config_file is None else config_file

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    value = data.get("base_folder")

    if not isinstance(value, str) or not value.strip():
        return None

    return Path(value)


def save_config(base_folder: Path, config_file: Path | None = None) -> None:
    """Writes the base folder to the config file, atomically.

    The file is written under a temporary name in the same folder and moved
    into place with `os.replace`, so a reader never sees half a file and a
    failed write leaves no temporary file behind.

    Args:
        base_folder: the folder to save.
        config_file: the file to write, the platform default when None.
    """
    target = config_path() if config_file is None else config_file
    target.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"base_folder": str(base_folder)}, handle)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_last_path() -> str | None:
    """Reads the last folder the GUI saved, if PySide6 is available.

    Returns:
        The saved folder, or None when there is none or no Qt to ask.
    """
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        return None

    value = QSettings("mktsk", "mktsk").value("last_path")

    if not isinstance(value, str) or not value.strip():
        return None

    return value


def migrate_from_qsettings(config_file: Path | None = None) -> Path | None:
    """Copies the folder the GUI saved into the config file, once.

    The old value is only read, never changed or removed. A config file that
    is already there is left alone, so the migration happens at most once. A
    folder that no longer exists is saved all the same, so the missing state
    can name it.

    Args:
        config_file: the file to write, the platform default when None.

    Returns:
        The migrated folder, or None when there was nothing to migrate.
    """
    target = config_path() if config_file is None else config_file

    if target.exists():
        return None

    last_path = _read_last_path()

    if last_path is None:
        return None

    folder = Path(last_path)
    save_config(folder, target)

    return folder


def resolve_base_folder(config_file: Path | None = None) -> BaseFolder:
    """Resolves the saved base folder and says whether it can be used.

    When no config file exists yet, the folder the GUI saved is migrated first.

    Args:
        config_file: the file to read, the platform default when None.

    Returns:
        The state of the base folder, and its path when one is saved.
    """
    target = config_path() if config_file is None else config_file

    if not target.exists():
        migrate_from_qsettings(target)

    folder = load_config(target)

    if folder is None:
        return BaseFolder(BaseFolderState.NOT_CONFIGURED)

    if not folder.is_dir():
        return BaseFolder(BaseFolderState.MISSING, folder)

    return BaseFolder(BaseFolderState.OK, folder)


def validate_category(
    name: str,
    categories: Iterable[str] = (),
) -> str:
    """Cleans a category name and refuses one that cannot be used.

    Args:
        name: the name as typed by the user.
        categories: the categories already chosen, for the duplicate check.

    Returns:
        The cleaned name.

    Raises:
        ValueError: when the name is empty, carries a character Windows does
            not allow, is reserved, is hidden, looks like a task folder, ends
            in a dot or a space, or repeats another category.
    """
    cleaned = name.strip()

    if not cleaned:
        raise ValueError("category name must not be empty")

    if any(char in _WINDOWS_FORBIDDEN for char in cleaned):
        raise ValueError(f"'{cleaned}' has a character Windows does not allow in a name")

    if any(ord(char) < 32 for char in cleaned):
        raise ValueError(f"'{cleaned}' has a character Windows does not allow in a name")

    if helpers.is_reserved_name(cleaned):
        raise ValueError(f"'{cleaned}' is a reserved name")

    if cleaned.startswith((".", "_")):
        raise ValueError("category name must not start with a dot or an underscore")

    if standards.is_task_folder(cleaned) or standards._reserved_task_title(cleaned):
        raise ValueError("category name must not look like a task folder")

    if cleaned != cleaned.rstrip(" ."):
        raise ValueError("category name must not end in a dot or a space")

    if any(cleaned.casefold() == other.strip().casefold() for other in categories):
        raise ValueError(f"'{cleaned}' is already a category")

    return cleaned


def run_setup(
    base_folder: str | Path,
    categories: Iterable[str] = (),
    *,
    config_path: Path | None = None,
) -> Path:
    """Sets up the base folder, its categories and the config file.

    Everything is validated before anything is created, and the config file is
    written only after the folders exist, so a failure leaves the old config
    untouched.

    Args:
        base_folder: the folder to keep tasks in.
        categories: at most two names to create inside it.
        config_path: the file to write, the platform default when None.

    Returns:
        The resolved base folder.

    Raises:
        ValueError: when the base folder is empty or a category cannot be used.
        OSError: when the folders cannot be created.
    """
    raw = str(base_folder).strip()

    if not raw:
        raise ValueError("base folder must not be empty")

    folder = Path(raw).expanduser().resolve()

    names = list(categories)
    if len(names) > MAXIMUM_CATEGORIES:
        raise ValueError(f"at most {MAXIMUM_CATEGORIES} categories are allowed")

    validated: list[str] = []
    for name in names:
        validated.append(validate_category(name, validated))

    folder.mkdir(parents=True, exist_ok=True)
    for name in validated:
        (folder / name).mkdir(exist_ok=True)

    save_config(folder, config_path)

    return folder
