"""The system tray icon and its menu, so closing hides instead of quitting.

There are no notifications and no timers: the tray only offers `Open` and a
real `Quit`, and shows or hides the window.
"""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .app_icon import app_icon


def tray_available() -> bool:
    """Whether the platform offers a system tray, so tests can patch it."""
    return QSystemTrayIcon.isSystemTrayAvailable()


class TrayController:
    """Owns the tray icon, its `Open`/`Quit` menu and its activation."""

    def __init__(self, window) -> None:
        self.window = window
        self.tray = QSystemTrayIcon(app_icon())
        self.tray.setToolTip("mktsk")
        self.tray.activated.connect(self._activated)
        self.tray.setContextMenu(self._menu())
        self.tray.show()

    def _menu(self) -> QMenu:
        menu = QMenu()
        open_action = QAction("Open", menu)
        open_action.triggered.connect(self._show)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.window.quit_application)
        menu.addAction(open_action)
        menu.addAction(quit_action)
        return menu

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show()

    def _show(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
