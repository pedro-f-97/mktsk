"""The read-only preview under the task table."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from mktsk.tasks import close_task
from tests.gui_helpers import (
    click_heading,
    select_tab,
    select_task,
    task_listing,
)


def test_nothing_selected_hides_the_preview(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    assert window.preview_area.isHidden() is True


def test_selecting_a_task_shows_the_text_of_its_md(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert window.preview_area.isHidden() is False
    assert window.preview_text.isReadOnly() is True
    assert window.preview_text.toPlainText() == "# 18/09/2026\n\nThe body\n"


def test_selecting_a_task_lists_the_names_of_its_attachments(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    (file.parent / "Attachments").mkdir()
    window.navigate_to(tmp_path)

    select_task(window, file)

    names = [
        window.preview_list.item(index).text()
        for index in range(window.preview_list.count())
    ]
    assert names == ["Attachments/", "one.pdf"]
    assert window.preview_list.isHidden() is False


def test_the_attachment_list_is_not_interactive(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    assert window.preview_list.selectionMode() == QListWidget.SelectionMode.NoSelection
    assert window.preview_list.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert window.preview_text.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert window.preview_list.contextMenuPolicy() == (
        Qt.ContextMenuPolicy.NoContextMenu
    )
    assert window.preview_list.toolTip() == ""
    assert all(
        window.preview_list.item(index).toolTip() == ""
        for index in range(window.preview_list.count())
    )


def test_the_attachment_list_is_striped(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    assert window.preview_list.alternatingRowColors() is True
    assert window.preview_list.selectionMode() == QListWidget.SelectionMode.NoSelection
    assert window.preview_list.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_a_task_without_attachments_hides_the_attachment_list(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert window.preview_area.isHidden() is False
    assert window.preview_list.isHidden() is True


def test_selecting_a_category_separator_hides_the_preview(
    window, tmp_path, make_task
):
    file = make_task(tmp_path / "Veritas", "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    select_task(window, file)

    # the first row of `All` is the heading of the category, which is where a
    # click lands and where the selection goes through the same path
    listing.setCurrentItem(listing.item(0))

    assert window.preview_area.isHidden() is True


def test_escape_hides_the_preview(qtbot, window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    listing.setFocus()

    qtbot.keyClick(listing, Qt.Key.Key_Escape)

    assert window.preview_area.isHidden() is True


def test_a_missing_md_shows_empty_text(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    select_task(window, foo)
    foo.unlink()

    select_task(window, bar)
    select_task(window, foo)

    assert window.preview_area.isHidden() is False
    assert window.preview_text.toPlainText() == ""


def test_a_closed_task_shows_an_empty_preview(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    # the folder is gone and the archive is never opened, so there is nothing
    # to preview and nothing beside the task to list
    assert window.preview_area.isHidden() is False
    assert window.preview_text.toPlainText() == ""
    assert window.preview_list.isHidden() is True


def test_a_reload_re_renders_the_preview_of_the_selected_task(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, file)
    file.write_text("# 18/09/2026\n\nChanged body\n", encoding="utf-8")

    # a reload of the rows that keeps the task selected re-reads the folder
    click_heading(window, 0)

    assert window.preview_area.isHidden() is False
    assert window.preview_text.toPlainText() == "# 18/09/2026\n\nChanged body\n"


def test_refresh_hides_the_preview_with_the_selection_it_drops(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, file)

    window.refresh()

    assert window.preview_area.isHidden() is True


def test_the_preview_shares_the_room_with_the_table(qtbot, window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)
    qtbot.wait(1)

    heights = window.table_splitter.sizes()
    widths = window.preview_area.sizes()

    assert heights[0] > 0 and heights[1] > 0
    assert heights[0] > heights[1]
    assert widths[0] > 0 and widths[1] > 0
    assert widths[0] > widths[1]
