"""The desktop interface, over the task logic the CLI uses.

The modules below carry one responsibility each: `icons` draws the icons,
`tree` lists the categories, `tasklist` lists the tasks of one of them,
`first_run` settles the base folder before the window opens, `single_instance`
keeps one running instance at a time, `tray` puts the window in the system
tray, and `window` puts the rest together.
"""

from PySide6.QtWidgets import QApplication, QMessageBox

from mktsk.reminders import reminders_path

from .first_run import ensure_base_folder
from .reminders_scheduler import ReminderScheduler
from .single_instance import acquire_instance_lock
from .tray import TrayController, tray_available
from .window import MainWindow

__all__ = ["MainWindow", "main"]


def main() -> int:
    """Runs the desktop interface."""
    app = QApplication([])
    base_folder = ensure_base_folder()

    if base_folder is None:
        return 1

    # one running instance at a time; acquire the lock before opening the
    # window, and keep it alive for the whole run
    lock = acquire_instance_lock(base_folder)
    if lock is None:
        QMessageBox.information(
            None,
            "mktsk",
            "mktsk is already running. Look for its icon in the system tray.",
        )
        return 0

    window = MainWindow(base_folder=base_folder)
    window._instance_lock = lock

    window.show()

    if tray_available():
        tray = TrayController(window)
        window.tray_controller = tray
        QApplication.setQuitOnLastWindowClosed(False)
        scheduler = ReminderScheduler(tray, reminders_path())
        scheduler.check()
        scheduler.start()

    return app.exec()
