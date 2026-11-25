"""The window title bar: window icon, title and the three window buttons.

This is the skeleton of the custom title bar. The three buttons are plain
placeholders: they carry no icons and are not connected to anything yet.
"""

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

from .icons import (
    _draw_maximize,
    _draw_minimize,
    _draw_restore,
    _draw_window_close,
    _icon_button,
    _IconButton,
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

        self._window = window
        self._drag_pending = False
        window.windowTitleChanged.connect(self._on_window_title_changed)
        window.installEventFilter(self)

        self.minimize_button = _icon_button(
            self, "Minimize", _draw_minimize, "titlebar-minimize"
        )
        self.minimize_button.setObjectName("titlebar-minimize")
        self.minimize_button.clicked.connect(window.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = cast(
            _IconButton,
            _icon_button(self, "Maximize", _draw_maximize, "titlebar-maximize"),
        )
        self.maximize_button.setObjectName("titlebar-maximize")
        self.maximize_button.clicked.connect(self._on_maximize_clicked)
        layout.addWidget(self.maximize_button)

        self.close_button = _icon_button(
            self, "Close", _draw_window_close, "titlebar-close"
        )
        self.close_button.setObjectName("titlebar-close")
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.close_button)

        self._sync_maximize_button()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """React to window state changes without swallowing any event."""
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_maximize_button()
        return False

    def _on_maximize_clicked(self) -> None:
        """Toggles between maximized and normal, following the window state."""
        self._toggle_maximize()

    def _toggle_maximize(self) -> None:
        """Toggles between maximized and normal, following the window state."""
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def _on_window_title_changed(self, title: str) -> None:
        """Keeps the title label in step with the window title."""
        self.title_label.setText(title)

    def _sync_maximize_button(self) -> None:
        """Sets the maximize button's icon and tooltip to match the window."""
        if self._window.isMaximized():
            self._set_maximize_button(_draw_restore, "Restore")
        else:
            self._set_maximize_button(_draw_maximize, "Maximize")

    def _set_maximize_button(
        self, draw: Callable[[QPainter, QRectF], None], tooltip: str
    ) -> None:
        """Swaps the maximize button's drawer and redraws it for the palette.

        Updating the drawer and re-running :meth:`_IconButton._apply_icon`
        keeps palette-change redraw working:
        :meth:`_IconButton.changeEvent` re-uses the drawer whenever the theme
        switches.
        """
        button = self.maximize_button
        button._draw = draw
        button._apply_icon()
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Records a drag started with the left button and accepts it."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pending = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Delegates the move to the operating system, once per press."""
        if self._drag_pending and event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_pending = False
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Cancels a pending drag when the button is released."""
        self._drag_pending = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Toggles maximized/normal on a left-button double click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
