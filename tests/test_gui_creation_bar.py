"""The creation bar sits above the task table in the right pane.

The tests read the rectangles the layout hands out, so they prove where the
bar sits, never how it looks.
"""

from freezegun import freeze_time
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication


def _left(widget, ancestor):
    """The left edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).x()


def _right(widget, ancestor):
    """The edge just past the right of a widget, in an ancestor's coordinates."""
    return widget.mapTo(ancestor, QPoint(widget.width(), 0)).x()


def _top(widget, ancestor):
    """The top edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, 0)).y()


def _bottom(widget, ancestor):
    """The bottom edge of a widget in the coordinates of an ancestor."""
    return widget.mapTo(ancestor, QPoint(0, widget.height())).y()


def _resize(window, width):
    window.resize(width, window.height())
    QApplication.processEvents()


def test_the_bar_sits_above_the_tabs(window):
    assert _bottom(window.bottom_bar, window.right_panel) <= _top(
        window.tabs, window.right_panel
    )


def test_the_bar_stays_inside_the_right_pane(window):
    assert _left(window.bottom_bar, window) >= _right(window.left_panel, window)
    assert _right(window.bottom_bar, window.right_panel) <= window.right_panel.width()


def test_the_bar_keeps_its_place_when_the_window_is_resized(window):
    for width in (window.width() - 120, window.width() + 200):
        _resize(window, width)

        assert _bottom(window.bottom_bar, window.right_panel) <= _top(
            window.tabs, window.right_panel
        )
        assert _left(window.bottom_bar, window) >= _right(window.left_panel, window)
        assert (
            _right(window.bottom_bar, window.right_panel) <= window.right_panel.width()
        )


@freeze_time("2026-09-30")
def test_creating_a_task_through_the_bar_still_works(
    window, qtbot, tmp_path, fake_open
):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Preview Task")

    qtbot.mouseClick(window.create_button, Qt.MouseButton.LeftButton)

    folder = tmp_path / "260930 - PreviewTask"
    file = folder / "PreviewTask.md"
    assert file.is_file()
    assert fake_open == [file]
    assert window.title_input.text() == ""
