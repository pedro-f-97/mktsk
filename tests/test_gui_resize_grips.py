"""Tests for the edge resize grips."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from mktsk.gui.resize_grips import ResizeGrip, cursor_for_edges


def _press(grip, button):
    """Sends a mouse button press to the grip."""
    QApplication.sendEvent(
        grip,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(),
            QPointF(),
            button,
            button,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def _patch_window_handle(window, monkeypatch):
    """Patches windowHandle to return a mock handle and returns it."""
    handle = Mock()
    monkeypatch.setattr(window, "windowHandle", lambda: handle)
    return handle


@pytest.mark.parametrize(
    "edges, expected",
    [
        (Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor),
        (Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor),
        (Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor),
        (Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor),
        (
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            Qt.CursorShape.SizeFDiagCursor,
        ),
        (
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
            Qt.CursorShape.SizeFDiagCursor,
        ),
        (
            Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            Qt.CursorShape.SizeBDiagCursor,
        ),
        (
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
            Qt.CursorShape.SizeBDiagCursor,
        ),
    ],
)
def test_cursor_for_edges_returns_expected_shape(edges, expected):
    assert cursor_for_edges(edges) == expected


@pytest.mark.parametrize(
    "edges",
    [
        Qt.Edge(0),
        Qt.Edge.LeftEdge | Qt.Edge.RightEdge,
        Qt.Edge.TopEdge | Qt.Edge.BottomEdge,
        Qt.Edge.TopEdge | Qt.Edge.LeftEdge | Qt.Edge.RightEdge,
    ],
)
def test_cursor_for_edges_raises_for_invalid_edges(edges):
    with pytest.raises(ValueError):
        cursor_for_edges(edges)


@pytest.mark.parametrize(
    "edges, expected",
    [
        (Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor),
        (
            Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            Qt.CursorShape.SizeBDiagCursor,
        ),
    ],
)
def test_grip_cursor_matches_edges(qapp, edges, expected):
    window = QWidget()
    grip = ResizeGrip(window, edges)
    assert grip.cursor().shape() == expected


@pytest.mark.parametrize(
    "edges",
    [
        Qt.Edge.LeftEdge,
        Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    ],
)
def test_left_press_calls_start_system_resize_once(qapp, monkeypatch, edges):
    window = QWidget()
    handle = _patch_window_handle(window, monkeypatch)
    grip = ResizeGrip(window, edges)

    _press(grip, Qt.MouseButton.LeftButton)
    handle.startSystemResize.assert_called_once_with(edges)


def test_right_press_does_not_call_start_system_resize(qapp, monkeypatch):
    window = QWidget()
    handle = _patch_window_handle(window, monkeypatch)
    grip = ResizeGrip(window, Qt.Edge.LeftEdge)

    _press(grip, Qt.MouseButton.RightButton)
    handle.startSystemResize.assert_not_called()


def test_left_press_with_no_window_handle_does_not_raise(qapp, monkeypatch):
    window = QWidget()
    monkeypatch.setattr(window, "windowHandle", lambda: None)
    grip = ResizeGrip(window, Qt.Edge.LeftEdge)

    _press(grip, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize(
    "edges",
    [
        Qt.Edge.LeftEdge,
        Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    ],
)
def test_edges_property(qapp, edges):
    window = QWidget()
    grip = ResizeGrip(window, edges)
    assert grip.edges == edges
