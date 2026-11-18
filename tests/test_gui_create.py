import shutil
from pathlib import Path

from freezegun import freeze_time
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from mktsk.config import BaseFolder, BaseFolderState
from mktsk.gui import MainWindow
from tests.gui_helpers import (
    select_directory,
    select_tab,
    tab_labels,
    tab_titles,
    tree_root,
)


def test_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("Could not open: /somewhere")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)

    window.open_with_default_app(tmp_path / "a.md")

    # the window shows the error as it is, the helper already words it
    assert fake_messages["warning"] == ["Could not open: /somewhere"]


@freeze_time("2026-09-28")
def test_create_task(qtbot, window, tmp_path, fake_open):
    window.navigate_to(tmp_path)
    qtbot.keyClicks(window.title_input, "Test Task")
    qtbot.keyClick(window.title_input, Qt.Key.Key_Return)

    folder = tmp_path / "260928 - TestTask"
    file = folder / "TestTask.md"
    assert file.is_file()
    assert file.read_text(encoding="utf-8") == (
        '# 28/09/2026\n\n\n[mktsk:2026-09-28T00:00]: # "open"\n'
    )
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert "28/09/2026  Test Task" in tab_labels(window, tmp_path.name)


def test_create_task_empty_title(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.create_task()

    assert fake_messages["critical"] == ["Invalid task description."]
    assert list(tmp_path.iterdir()) == []


def test_create_task_empty_standardized(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("!!!")

    window.create_task()

    assert fake_messages["critical"] == ["invalid task description"]
    assert list(tmp_path.iterdir()) == []


def test_create_task_reserved_name(window, tmp_path, fake_messages):
    window.navigate_to(tmp_path)
    window.title_input.setText("con")

    window.create_task()

    assert fake_messages["critical"] == ["'Con' is a reserved name"]
    assert list(tmp_path.iterdir()) == []


@freeze_time("2026-09-28")
def test_create_task_resumes_existing_task(window, tmp_path, fake_open):
    existing_folder = tmp_path / "260928 - TestTask"
    existing_folder.mkdir()
    existing_file = existing_folder / "TestTask.md"
    # a file with nothing in it is dated, so the visit has a section of its own
    existing_file.write_text("", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert existing_file.read_text(encoding="utf-8") == (
        '# 28/09/2026\n\n\n[mktsk:2026-09-28T00:00]: # "in-progress"\n'
    )
    assert fake_open == [existing_file]


@freeze_time("2026-09-30")
def test_create_task_finds_existing_task_by_title(window, tmp_path, fake_open):
    folder = tmp_path / "260918 - TestTask"
    folder.mkdir()
    file = folder / "TestTask.md"
    file.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert file.read_text(encoding="utf-8") == (
        "# 18/09/2026\n\nnotes\n\n# 30/09/2026\n\n\n"
        '[mktsk:2026-09-30T00:00]: # "in-progress"\n'
    )
    assert fake_open == [file]
    assert window.title_input.text() == ""
    assert not (tmp_path / "260930 - TestTask").exists()


@freeze_time("2026-09-30")
def test_create_task_creates_when_task_is_in_a_subdirectory(window, tmp_path, fake_open):
    subdirectory = tmp_path / "Veritas"
    subdirectory.mkdir()
    folder = subdirectory / "260918 - TestTask"
    folder.mkdir()
    existing = folder / "TestTask.md"
    existing.write_text("# 18/09/2026\n\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    created = tmp_path / "260930 - TestTask" / "TestTask.md"

    assert created.is_file()
    assert fake_open == [created]
    assert existing.read_text(encoding="utf-8") == "# 18/09/2026\n\n"


@freeze_time("2026-09-30")
def test_create_task_lands_in_the_base_folder_tab(window, tmp_path, fake_open, make_task):
    make_task(tmp_path / "Veritas", "260918", "Other")
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert (tmp_path / "260930 - TestTask" / "TestTask.md").is_file()
    assert not (tmp_path / "Veritas" / "260930 - TestTask").exists()
    assert tab_labels(window, tmp_path.name) == ["30/09/2026  Test Task"]


@freeze_time("2026-09-28")
def test_create_task_open_failure_warns(window, tmp_path, monkeypatch, fake_messages):
    def raise_error(path):
        raise OSError("boom")

    monkeypatch.setattr("mktsk.helpers.open_file", raise_error)
    window.navigate_to(tmp_path)
    window.title_input.setText("Test Task")

    window.create_task()

    assert fake_messages["critical"] == []
    assert len(fake_messages["warning"]) == 1
    assert (tmp_path / "260928 - TestTask" / "TestTask.md").is_file()
    assert window.title_input.text() == ""


@freeze_time("2026-09-30")
def test_create_task_lands_in_the_selected_category(window, tmp_path, fake_open):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    created = category / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]
    assert not (tmp_path / "260930 - TestTask").exists()
    assert window.title_input.text() == ""
    assert window.current_directory == tmp_path.resolve()


@freeze_time("2026-09-30")
def test_create_task_twice_keeps_the_selected_category(window, tmp_path, fake_open):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())

    window.title_input.setText("Test Task")
    window.create_task()
    window.title_input.setText("Other Task")
    window.create_task()

    assert (category / "260930 - TestTask" / "TestTask.md").is_file()
    assert (category / "260930 - OtherTask" / "OtherTask.md").is_file()
    assert window.creation_directory() == category.resolve()


@freeze_time("2026-09-30")
def test_create_task_looks_the_title_up_inside_the_selected_category(
    window, tmp_path, fake_open
):
    category = tmp_path / "Veritas"
    category.mkdir()
    folder = tmp_path / "260918 - TestTask"
    folder.mkdir()
    outside = folder / "TestTask.md"
    outside.write_text("# 18/09/2026\n\nnotes\n", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    created = category / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]
    assert outside.read_text(encoding="utf-8") == "# 18/09/2026\n\nnotes\n"


@freeze_time("2026-09-30")
def test_create_task_in_a_category_keeps_the_active_tab(window, tmp_path, fake_open, make_task):
    make_task(tmp_path / "Veritas", "260918", "Other")
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, tmp_path.name)
    select_directory(window, (tmp_path / "Veritas").resolve())
    window.title_input.setText("Test Task")

    window.create_task()

    assert window.tabs.tabText(window.tabs.currentIndex()) == tmp_path.name
    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]


# The creation bar sits above the task table in the right pane.
#
# The tests read the rectangles the layout hands out, so they prove where the
# bar sits, never how it looks.


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


def test_creation_directory_without_a_selection(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    assert window.creation_directory() == tmp_path.resolve()


def test_creation_directory_with_the_root_selected(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    window.directory_tree.setCurrentItem(tree_root(window))

    assert window.creation_directory() == tmp_path.resolve()


def test_creation_directory_with_a_category_selected(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.creation_directory() == (tmp_path / "Veritas").resolve()
    assert window.current_directory == tmp_path.resolve()


def test_target_line_is_hidden_without_a_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    assert window.target_label.isVisible() is False


def test_target_line_is_hidden_on_the_root(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    window.directory_tree.setCurrentItem(tree_root(window))

    assert window.target_label.isVisible() is False


def test_target_line_names_the_selected_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()

    select_directory(window, category)

    # the path label above already names the base directory
    assert window.target_label.text() == "New tasks in Veritas"
    assert window.target_label.toolTip() == str(category)
    assert window.target_label.isVisible() is True


def test_the_target_hint_stays_readable_in_dark_mode(tmp_path, qapp, qtbot, monkeypatch):
    monkeypatch.setattr(
        "mktsk.config.resolve_base_folder",
        lambda: BaseFolder(BaseFolderState.OK, Path.cwd()),
    )

    original = qapp.palette()
    try:
        dark = QPalette()
        dark.setColor(QPalette.ColorRole.Base, QColor("#101010"))
        dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        dark.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        dark.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        qapp.setPalette(dark)
        QApplication.processEvents()

        settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        win = MainWindow(settings=settings)
        win.show()
        qtbot.addWidget(win)

        category = tmp_path / "Veritas"
        category.mkdir()
        win.navigate_to(tmp_path)
        select_directory(win, category.resolve())

        assert win.target_label.isVisible() is True
        assert win.target_label.text() == "New tasks in Veritas"

        # In dark mode PlaceholderText is black, which disappears on the dark
        # base; the hint must keep the readable text colour instead.
        colour = win.target_label.palette().color(QPalette.ColorRole.WindowText)
        assert colour == dark.color(QPalette.ColorRole.Text)
    finally:
        qapp.setPalette(original)


def test_target_line_stays_on_one_line(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.wordWrap() is False


def test_target_line_shares_the_row_of_the_title_field(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.y() == window.title_input.y()
    assert window.target_label.height() == window.title_input.height()
    assert window.target_label.fontMetrics().height() == (
        window.path_label.fontMetrics().height()
    )


def test_target_line_sits_between_the_title_field_and_create(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.target_label.x() >= window.title_input.x() + window.title_input.width()
    assert (
        window.target_label.x() + window.target_label.width()
        <= window.create_button.x()
    )


def test_target_line_hides_again_after_navigating_into_the_category(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.navigate_to(tmp_path / "Veritas")

    assert window.creation_directory() == (tmp_path / "Veritas").resolve()
    assert window.target_label.isVisible() is False


def test_target_line_hides_again_after_navigating_away(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    (tmp_path / "SteelMountain").mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, (tmp_path / "Veritas").resolve())

    window.navigate_to(tmp_path / "SteelMountain")

    assert window.creation_directory() == (tmp_path / "SteelMountain").resolve()
    assert window.target_label.isVisible() is False


def test_selecting_a_category_does_not_change_the_active_tab(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Bar")
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, tmp_path.name)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert window.tabs.tabText(window.tabs.currentIndex()) == tmp_path.name


def test_selecting_a_category_does_not_reload_the_tabs(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    before = tab_titles(window)

    select_directory(window, (tmp_path / "Veritas").resolve())

    assert tab_titles(window) == before


def test_the_tree_selection_survives_a_refresh(window, tmp_path):
    (tmp_path / "Veritas").mkdir()
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)

    window.refresh()

    assert window.creation_directory() == category
    assert window.target_label.isVisible() is True


def test_the_tree_selection_is_dropped_when_the_category_is_deleted(window, tmp_path):
    category = tmp_path / "Veritas"
    category.mkdir()
    window.navigate_to(tmp_path)
    select_directory(window, category.resolve())

    shutil.rmtree(category)
    window.refresh()

    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False
