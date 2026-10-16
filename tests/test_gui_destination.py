"""The destination of a new task: the tree, its label, the 'x' and the rows."""

import datetime

from freezegun import freeze_time
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QStyle

from mktsk.gui.tasklist import _ENTRY_ROLE
from tests.gui_helpers import (
    fill_task,
    find_directory,
    find_task,
    render_row,
    select_directory,
    select_tab,
    select_task,
    task_listing,
    tree_root,
)

# the room at the right end of a row that only a marker can ink: a category
# name is drawn from the left, so everything past it is bare without one
_MARKER_REGION = 20


def _separator(listing, title):
    """The category row with the given name, which carries no task."""
    for index in range(listing.count()):
        item = listing.item(index)
        if item.data(_ENTRY_ROLE) is None and item.text() == title:
            return item

    raise AssertionError(f"there is no {title} separator")


def _marker_pixels(listing, item):
    """The ink of the marker of a row, in the colour the header icons carry."""
    image = render_row(listing, item, QStyle.StateFlag.State_None)
    colour = listing.viewport().palette().color(QPalette.ColorRole.ButtonText)
    first = max(image.width() - _MARKER_REGION, 0)

    return sum(
        image.pixelColor(x, y) == colour
        for y in range(image.height())
        for x in range(first, image.width())
    )


def _click_row(qtbot, listing, item):
    """Clicks a row of a list, where a person would click it."""
    qtbot.mouseClick(
        listing.viewport(),
        Qt.MouseButton.LeftButton,
        pos=listing.visualItemRect(item).center(),
    )


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


def test_clicking_a_category_separator_selects_it_in_the_tree(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    separated = _separator(listing, "Veritas")
    select_task(window, tmp_path / "260918 - Foo" / "Foo.md")

    _click_row(qtbot, listing, separated)

    assert window.directory_tree.currentItem() == find_directory(
        window, category.resolve()
    )
    assert window.creation_directory() == category.resolve()
    assert window.target_label.isVisible() is True
    assert window.clear_target_button.isVisible() is True
    # a category row is not a task, so the selection and its bar go
    assert listing.selected_entry() is None
    assert listing.action_bar.isVisible() is False
    # and the heading now carries the marker of the destination
    assert _marker_pixels(listing, separated) > 0
    # and the tab in front stays the one it was
    assert window.tabs.tabText(window.tabs.currentIndex()) == "All"


def test_the_marker_follows_the_tree_selection(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    make_task(category, "260925", "Bar")
    other = tmp_path / "SteelMountain"
    make_task(other, "260924", "Baz")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    veritas = _separator(listing, "Veritas")
    steel = _separator(listing, "SteelMountain")

    assert _marker_pixels(listing, veritas) == 0
    assert _marker_pixels(listing, steel) == 0

    select_directory(window, category.resolve())

    assert _marker_pixels(listing, veritas) > 0
    assert _marker_pixels(listing, steel) == 0

    select_directory(window, other.resolve())

    assert _marker_pixels(listing, veritas) == 0
    assert _marker_pixels(listing, steel) > 0

    window.clear_target_button.click()

    assert _marker_pixels(listing, veritas) == 0
    assert _marker_pixels(listing, steel) == 0

    select_directory(window, category.resolve())
    window.refresh()
    listing = task_listing(window)

    assert _marker_pixels(listing, _separator(listing, "Veritas")) > 0
    assert _marker_pixels(listing, _separator(listing, "SteelMountain")) == 0

    # a base folder that does not hold the category drops it and its marker
    window.navigate_to(other)

    assert window.target_label.isVisible() is False
    listing = task_listing(window)
    assert _marker_pixels(listing, _separator(listing, "SteelMountain")) == 0


def test_the_marker_of_a_destination_without_a_row_is_nowhere(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    (tmp_path / "Empty").mkdir()
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    base = _separator(listing, tmp_path.name)

    select_directory(window, (tmp_path / "Empty").resolve())

    # the category is the destination, but no tab lists a row for it
    assert window.target_label.isVisible() is True
    assert [
        item.text()
        for item in listing.findItems("Empty", Qt.MatchFlag.MatchExactly)
    ] == []
    assert _marker_pixels(listing, base) == 0


def test_clicking_a_task_row_keeps_the_destination(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    file = make_task(tmp_path / "Veritas", "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)
    task_row = find_task(window, file)

    _click_row(qtbot, listing, task_row)

    assert window.directory_tree.currentItem() == find_directory(window, category)
    assert window.creation_directory() == category
    assert window.target_label.isVisible() is True
    assert listing.selected_entry() is not None


def test_clicking_an_archive_separator_changes_nothing(
    window, tmp_path, make_task, qtbot
):
    file = make_task(tmp_path / "Veritas", "260925", "Bar")
    fill_task(file, datetime.date(2026, 9, 25), "closed", 0)
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    category = (tmp_path / "Veritas").resolve()
    select_directory(window, category)
    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    heading = _separator(listing, "Veritas")

    _click_row(qtbot, listing, heading)

    assert window.directory_tree.currentItem() == find_directory(window, category)
    assert window.creation_directory() == category
    assert window.target_label.isVisible() is True


def test_clicking_the_selected_separator_keeps_the_destination(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    separated = _separator(listing, "Veritas")

    _click_row(qtbot, listing, separated)
    _click_row(qtbot, listing, separated)

    assert window.creation_directory() == category.resolve()
    assert window.target_label.isVisible() is True
    assert _marker_pixels(listing, separated) > 0


@freeze_time("2026-09-30")
def test_escape_clears_the_task_and_the_destination(
    window, tmp_path, make_task, qtbot, fake_open
):
    file = make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    separated = _separator(listing, "Veritas")
    select_directory(window, category.resolve())
    select_task(window, file)
    listing.setFocus()

    assert listing.action_bar.isVisible() is True
    assert window.target_label.isVisible() is True
    assert _marker_pixels(listing, separated) > 0

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert listing.currentItem() is None
    assert listing.action_bar.isVisible() is False
    assert window.directory_tree.currentItem() is None
    assert window.target_label.isVisible() is False
    assert window.clear_target_button.isVisible() is False
    assert _marker_pixels(listing, separated) == 0

    window.title_input.setText("Test Task")
    window.create_task()

    created = tmp_path / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]


def test_escape_with_only_a_destination_clears_it(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    category = (tmp_path / "Veritas").resolve()
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    select_directory(window, category)
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert window.directory_tree.currentItem() is None
    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False
    assert window.clear_target_button.isVisible() is False


def test_escape_with_nothing_selected_changes_nothing(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert listing.currentItem() is None
    assert window.directory_tree.currentItem() is None
    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False


def test_escape_in_the_title_field_keeps_the_destination(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    category = (tmp_path / "Veritas").resolve()
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    select_directory(window, category)
    window.title_input.setFocus()

    qtbot.keyClick(window.title_input, Qt.Key.Key_Escape)

    assert window.directory_tree.currentItem() == find_directory(window, category)
    assert window.creation_directory() == category
    assert window.target_label.isVisible() is True


def test_escape_clears_the_destination_with_the_left_pane_collapsed(
    window, tmp_path, make_task, qtbot
):
    make_task(tmp_path, "260918", "Foo")
    category = (tmp_path / "Veritas").resolve()
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    select_directory(window, category)
    window.toggle_left_pane()
    listing.setFocus()

    assert window.splitter.sizes()[0] == 0

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert window.directory_tree.currentItem() is None
    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False


@freeze_time("2026-09-30")
def test_the_destination_works_with_the_left_pane_collapsed(
    window, tmp_path, make_task, qtbot, fake_open
):
    make_task(tmp_path, "260918", "Foo")
    category = tmp_path / "Veritas"
    make_task(category, "260925", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    window.toggle_left_pane()

    assert window.splitter.sizes()[0] == 0

    _click_row(qtbot, listing, _separator(listing, "Veritas"))

    assert window.creation_directory() == category.resolve()
    assert window.target_label.isVisible() is True
    window.title_input.setText("Test Task")
    window.create_task()
    created = category / "260930 - TestTask" / "TestTask.md"
    assert created.is_file()
    assert fake_open == [created]

    window.clear_target_button.click()

    assert window.creation_directory() == tmp_path.resolve()
    assert window.target_label.isVisible() is False
