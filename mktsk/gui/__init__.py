"""The desktop interface, over the task logic the CLI uses.

The modules below carry one responsibility each: `icons` draws the icons,
`tree` lists the categories, `tasklist` lists the tasks of one of them,
`first_run` settles the base folder before the window opens, and `window`
puts the rest together.
"""

from PySide6.QtWidgets import QApplication

from .first_run import ensure_base_folder
from .window import MainWindow

__all__ = ["MainWindow", "main"]


def main() -> int:
    """Runs the desktop interface."""
    app = QApplication([])
    base_folder = ensure_base_folder()

    if base_folder is None:
        return 1

    window = MainWindow(base_folder=base_folder)
    window.show()
    return app.exec()
