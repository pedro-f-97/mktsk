"""The window title bar: window icon, title and the three window buttons.

This is the skeleton of the custom title bar. The three buttons are plain
placeholders: they carry no icons and are not connected to anything yet.
"""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

TITLEBAR_HEIGHT = 32


class TitleBar(QWidget):
    """Horizontal bar showing the window icon and title, plus three buttons.

    The bar has a fixed height. The icon and title sit at the left, an
    expandable stretch pushes the minimize, maximize and close buttons to the
    right, and that stretch is the only extension point for now.

    Args:
        window: the top-level window whose icon and title the bar shows.
        parent: the parent widget of the bar, or None.
    """

    def __init__(self, window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLEBAR_HEIGHT)

        layout = QHBoxLayout(self)
        # small left margin, none on the right, no space between the buttons
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("titlebar-icon")
        self.icon_label.setPixmap(window.windowIcon().pixmap(QSize(16, 16)))
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(window.windowTitle(), self)
        self.title_label.setObjectName("titlebar-title")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.minimize_button = QToolButton(self)
        self.minimize_button.setObjectName("titlebar-minimize")
        self.minimize_button.setToolTip("Minimize")
        layout.addWidget(self.minimize_button)

        self.maximize_button = QToolButton(self)
        self.maximize_button.setObjectName("titlebar-maximize")
        self.maximize_button.setToolTip("Maximize")
        layout.addWidget(self.maximize_button)

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("titlebar-close")
        self.close_button.setToolTip("Close")
        layout.addWidget(self.close_button)
