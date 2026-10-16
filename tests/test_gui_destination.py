"""The 'x' on the new-task destination label, and where a task lands after it."""

from freezegun import freeze_time
from PySide6.QtCore import QPoint, Qt

from tests.gui_helpers import select_directory, tree_root


def test_the_clear_button_carries_a_cross_and_a_tooltip(window):
    button = window.clear_target_button

    assert button.text() == ""
    assert button.icon().isNull() is False
    assert button.toolTip() == "Clear destination"
    assert button.autoRaise() is True
    assert button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_the_clear_button_is_shown_with_the_target_line(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    assert window.target_label.isVisible() is False
    assert window.clear_target_button.isVisible() is False

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.isVisible() is True
    assert window.clear_target_button.isVisible() is True


def test_the_clear_button_is_hidden_on_the_root(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.directory_tree.setCurrentItem(tree_root(window))

    assert window.target_label.isVisible() is False
    assert window.clear_target_button.isVisible() is False


def test_the_clear_button_drops_the_destination(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.clear_target_button.click()

    assert window.directory_tree.currentItem() is None
    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False
    assert window.clear_target_button.isVisible() is False


@freeze_time("2026-09-30")
def test_a_task_created_after_clearing_lands_in_the_base_directory(
    window, tmp_path, fake_open
):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.clear_target_button.click()
    window.title_input.setText("Test Task")
    window.create_task()

    created = tmp_path / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]
    assert not (tmp_path / "Veritas" / "260930 - TestTask").exists()


def test_the_clear_button_keeps_the_shape_of_the_creation_bar(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())
    bar = window.bottom_bar
    button = window.clear_target_button
    header = window.directory_tree.header_view

    # small and flat at the top of the row, so the bar is still as tall as
    # the title field and the Create button make it
    assert button.y() == 0
    assert bar.sizeHint().height() == max(
        window.title_input.sizeHint().height(),
        window.create_button.sizeHint().height(),
    )
    # and the bar still starts on the line the Directory header starts on
    assert bar.mapTo(window, QPoint(0, 0)).y() == header.mapTo(window, QPoint(0, 0)).y()
