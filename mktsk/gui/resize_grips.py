"""Resize grips for the edges and corners of a window.

Each grip is a small invisible widget: it shows the resize cursor of its
edge and asks the operating system to start a resize when it is pressed.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget


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
