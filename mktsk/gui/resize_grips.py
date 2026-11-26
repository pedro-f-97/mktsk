"""Resize grips for the edges and corners of a window.

Each grip is a small invisible widget: it shows the resize cursor of its
edge and asks the operating system to start a resize when it is pressed.
"""

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget

GRIP_THICKNESS = 5
GRIP_CORNER = 10


def cursor_for_edges(edges: Qt.Edge) -> Qt.CursorShape:
    """Returns the resize cursor for a set of window edges.

    Args:
        edges: one or more edges of Qt.Edge.

    Returns:
        The cursor shape that matches the edges: horizontal for a single
        vertical edge, vertical for a single horizontal edge, and diagonal
        for the two diagonal corner pairs.

    Raises:
        ValueError: when the edges describe no edge, both edges of an axis,
                    three edges or four edges.
    """
    if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
        return Qt.CursorShape.SizeHorCursor
    if edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
        return Qt.CursorShape.SizeVerCursor
    if edges in (
        Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
        Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
    ):
        return Qt.CursorShape.SizeFDiagCursor
    if edges in (
        Qt.Edge.TopEdge | Qt.Edge.RightEdge,
        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
    ):
        return Qt.CursorShape.SizeBDiagCursor
    raise ValueError(f"unsupported edge combination: {edges!r}")


class ResizeGrip(QWidget):
    """A grip on one edge or corner of the window.

    The grip draws nothing and shows the resize cursor of its edges. A
    left-button press asks the operating system to start a resize right
    away, with no drag threshold; any other button falls back to the base
    implementation.

    Args:
        window: the top-level window the grip resizes.
        edges: the edge or corner of the window the grip stands on.
        parent: the parent widget of the grip, or None.
    """

    def __init__(
        self, window: QWidget, edges: Qt.Edge, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._edges = edges
        self.setCursor(cursor_for_edges(edges))

    @property
    def edges(self) -> Qt.Edge:
        """The edge or corner of the window the grip stands on."""
        return self._edges

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Starts a system resize on a left-button press."""
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemResize(self._edges)
            event.accept()
        else:
            super().mousePressEvent(event)


class ResizeGrips(QObject):
    """Places eight ResizeGrip widgets along the edges and corners of a parent.

    The grips follow the parent's size and are hidden while the window is
    maximized. The QObject's own parent is `parent`.

    Args:
        window: the top-level window the grips resize.
        parent: the widget the grips are placed in.
    """

    def __init__(self, window: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self._window = window
        self._parent = parent
        edges = (
            Qt.Edge.TopEdge,
            Qt.Edge.BottomEdge,
            Qt.Edge.LeftEdge,
            Qt.Edge.RightEdge,
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
        )
        self._grips = tuple(ResizeGrip(window, edge, parent) for edge in edges)
        parent.installEventFilter(self)
        window.installEventFilter(self)
        self._position_grips()
        self._set_visibility()

    @property
    def grips(self) -> tuple:
        """The eight grip widgets, as a read-only tuple."""
        return self._grips

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """React to parent resizes and window state changes without swallowing."""
        if event.type() == QEvent.Type.Resize:
            self._position_grips()
        if event.type() == QEvent.Type.WindowStateChange:
            self._set_visibility()
        return False

    def _position_grips(self) -> None:
        """Places every grip on the parent's edges and corners, on top."""
        w = self._parent.width()
        h = self._parent.height()
        t = GRIP_THICKNESS
        c = GRIP_CORNER
        width = max(0, w - 2 * c)
        height = max(0, h - 2 * c)
        rectangles = {
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge: QRect(0, 0, c, c),
            Qt.Edge.TopEdge | Qt.Edge.RightEdge: QRect(w - c, 0, c, c),
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge: QRect(0, h - c, c, c),
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge: QRect(w - c, h - c, c, c),
            Qt.Edge.TopEdge: QRect(c, 0, width, t),
            Qt.Edge.BottomEdge: QRect(c, h - t, width, t),
            Qt.Edge.LeftEdge: QRect(0, c, t, height),
            Qt.Edge.RightEdge: QRect(w - t, c, t, height),
        }
        for grip in self._grips:
            grip.setGeometry(rectangles[grip.edges])
            grip.raise_()

    def _set_visibility(self) -> None:
        """Hides the grips while the window is maximized."""
        for grip in self._grips:
            grip.setVisible(not self._window.isMaximized())
