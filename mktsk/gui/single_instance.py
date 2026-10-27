"""A single-instance guard for the GUI, over a `QLockFile` beside the config.

Applies to the GUI only, never to the CLI, and regardless of tray availability.
"""

from pathlib import Path

from PySide6.QtCore import QLockFile

from mktsk import config


def acquire_instance_lock(directory: Path) -> QLockFile | None:
    """Tries to take the instance lock of the directory.

    The lock file is `mktsk.lock` in the same directory that `config.py` keeps
    the config file in, so the config path logic is reused rather than
    duplicated. `QLockFile`'s default stale-lock detection handles a lock left
    behind by a crashed process.

    Args:
        directory: the directory the lock belongs to.

    Returns:
        The locked `QLockFile`, which must be kept alive for the whole run, or
        `None` when another process already holds the lock.
    """
    lock_file = config.config_path().parent / "mktsk.lock"
    lock = QLockFile(str(lock_file))
    if not lock.tryLock(0):
        return None
    return lock
