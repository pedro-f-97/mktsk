"""Tests for the edge resize grips."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from mktsk.gui.resize_grips import (
    GRIP_CORNER,
    GRIP_THICKNESS,
    ResizeGrip,
    ResizeGrips,
    cursor_for_edges,
)


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


def _all_edge_combinations():
    return {
        Qt.Edge.TopEdge,
        Qt.Edge.BottomEdge,
        Qt.Edge.LeftEdge,
        Qt.Edge.RightEdge,
        Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
        Qt.Edge.TopEdge | Qt.Edge.RightEdge,
        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
        Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
    }


def _expected_rect(edges, w, h):
    """Returns the expected rectangle for a grip on `edges` at size wxh."""
    t = GRIP_THICKNESS
    c = GRIP_CORNER
    width = max(0, w - 2 * c)
    height = max(0, h - 2 * c)
    if edges == Qt.Edge.TopEdge | Qt.Edge.LeftEdge:
        return QRect(0, 0, c, c)
    if edges == Qt.Edge.TopEdge | Qt.Edge.RightEdge:
        return QRect(w - c, 0, c, c)
    if edges == Qt.Edge.BottomEdge | Qt.Edge.LeftEdge:
        return QRect(0, h - c, c, c)
    if edges == Qt.Edge.BottomEdge | Qt.Edge.RightEdge:
        return QRect(w - c, h - c, c, c)
    if edges == Qt.Edge.TopEdge:
        return QRect(c, 0, width, t)
    if edges == Qt.Edge.BottomEdge:
        return QRect(c, h - t, width, t)
    if edges == Qt.Edge.LeftEdge:
        return QRect(0, c, t, height)
    if edges == Qt.Edge.RightEdge:
        return QRect(w - t, c, t, height)
    raise AssertionError(f"unexpected edges: {edges!r}")


def test_eight_grips_are_children_of_parent(qapp):
    window = QWidget()
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    grips = list(manager.grips)
    assert len(grips) == 8
    for grip in grips:
        assert isinstance(grip, ResizeGrip)
        assert grip.parent() is parent
    assert {grip.edges for grip in grips} == _all_edge_combinations()


def test_grip_rectangles_at_200x100(qapp):
    window = QWidget()
    parent = QWidget()
    parent.resize(200, 100)
    parent.show()
    manager = ResizeGrips(window, parent)
    QApplication.sendEvent(parent, QEvent(QEvent.Type.Resize))
    for grip in manager.grips:
        assert grip.geometry() == _expected_rect(grip.edges, 200, 100)


def test_grip_rectangles_follow_new_size(qapp):
    window = QWidget()
    parent = QWidget()
    parent.show()
    manager = ResizeGrips(window, parent)
    parent.resize(300, 150)
    QApplication.sendEvent(parent, QEvent(QEvent.Type.Resize))
    for grip in manager.grips:
        assert grip.geometry() == _expected_rect(grip.edges, 300, 150)


def test_no_grip_has_negative_size_for_small_parent(qapp):
    window = QWidget()
    parent = QWidget()
    parent.resize(15, 15)
    parent.show()
    manager = ResizeGrips(window, parent)
    QApplication.sendEvent(parent, QEvent(QEvent.Type.Resize))
    for grip in manager.grips:
        rect = grip.geometry()
        assert rect.width() >= 0
        assert rect.height() >= 0


def test_grips_stay_on_top_after_adding_child(qapp):
    window = QWidget()
    parent = QWidget()
    parent.show()
    manager = ResizeGrips(window, parent)
    QWidget(parent)
    parent.resize(300, 150)
    QApplication.sendEvent(parent, QEvent(QEvent.Type.Resize))
    children = parent.children()
    grips = set(manager.grips)
    seen_grip = False
    for child in children:
        if child in grips:
            seen_grip = True
        elif seen_grip:
            raise AssertionError(f"non-grip child {child!r} comes after a grip")


def test_grips_not_hidden_when_not_maximized(qapp):
    window = QWidget()
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    for grip in manager.grips:
        assert not grip.isHidden()


def test_grips_hidden_when_maximized_at_construction(qapp, monkeypatch):
    window = QWidget()
    monkeypatch.setattr(window, "isMaximized", lambda: True)
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    for grip in manager.grips:
        assert grip.isHidden()


def test_window_state_change_hides_and_shows_grips(qapp, monkeypatch):
    window = QWidget()
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    monkeypatch.setattr(window, "isMaximized", lambda: True)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowStateChange))
    for grip in manager.grips:
        assert grip.isHidden()
    monkeypatch.setattr(window, "isMaximized", lambda: False)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowStateChange))
    for grip in manager.grips:
        assert not grip.isHidden()


def test_event_filter_returns_false(qapp):
    window = QWidget()
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    assert manager.eventFilter(parent, QEvent(QEvent.Type.Resize)) is False
    assert manager.eventFilter(window, QEvent(QEvent.Type.WindowStateChange)) is False
    assert manager.eventFilter(parent, QEvent(QEvent.Type.MouseButtonPress)) is False


def test_grips_property_returns_tuple_of_eight_resize_grips(qapp):
    window = QWidget()
    parent = QWidget()
    manager = ResizeGrips(window, parent)
    grips = manager.grips
    assert isinstance(grips, tuple)
    assert len(grips) == 8
    assert all(isinstance(grip, ResizeGrip) for grip in grips)
