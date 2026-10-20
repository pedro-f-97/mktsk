"""The Closed tab: the reopen button and the preview of a closed task."""

from PySide6.QtCore import QPoint

from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab


def _left_in(window, button):
    """The left edge of a button, in window coordinates."""
    return button.mapTo(window, QPoint(0, 0)).x()


def test_the_reopen_button_starts_where_the_first_action_starts(
    window, tmp_path, make_task
):
    active = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    close_task(tmp_path / "260919 - Bar", "Bar")
    window.navigate_to(tmp_path)

    open_left = _left_in(window, action_bar(window, active).open_button)

    select_tab(window, "Closed")
    closed_bar = action_bar(window, tmp_path / "260919 - Bar.zip", "Closed")

    assert _left_in(window, closed_bar.resume_button) == open_left


def test_the_reopen_button_is_not_centred_in_the_action_line(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")
    geometry = bar.resume_button.geometry()

    assert geometry.left() != (bar.width() - geometry.width()) // 2
