"""The desktop interface, over the task logic the CLI uses.

The modules below carry one responsibility each: `icons` draws the icons,
`tree` lists the categories, `tasklist` lists the tasks of one of them and
`window` puts the three together.
"""

from PySide6.QtWidgets import QApplication

from .window import MainWindow

__all__ = ["MainWindow", "main"]


def main() -> int:  # pragma: no cover
    """Runs the desktop interface."""
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
