"""The read-only preview under the task table."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from mktsk.tasks import close_task
from tests.gui_helpers import (
    action_bar,
    click_heading,
    directory_header,
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
    assert window.preview_area.preview_text.isReadOnly() is True
    assert window.preview_area.preview_text.toPlainText() == "# 18/09/2026\n\nThe body\n"


def test_selecting_a_task_lists_the_names_of_its_attachments(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    (file.parent / "Attachments").mkdir()
    window.navigate_to(tmp_path)

    select_task(window, file)

    names = [
        window.preview_area.preview_list.item(index).text()
        for index in range(window.preview_area.preview_list.count())
    ]
    assert names == ["Attachments/", "one.pdf"]
    assert window.preview_area.preview_list.isHidden() is False


def test_the_attachment_list_supports_single_selection_and_focus(
    window, tmp_path, make_task
):
    """The attachment list allows single-item selection and keyboard focus."""
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    assert window.preview_area.preview_list.selectionMode() == QListWidget.SelectionMode.SingleSelection
    assert window.preview_area.preview_list.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert window.preview_area.preview_text.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert window.preview_area.preview_list.contextMenuPolicy() == (
        Qt.ContextMenuPolicy.NoContextMenu
    )
    assert window.preview_area.preview_list.toolTip() == ""
    assert all(
        window.preview_area.preview_list.item(index).toolTip() == ""
        for index in range(window.preview_area.preview_list.count())
    )


def test_the_attachment_list_is_striped_and_selectable(window, tmp_path, make_task):
    """The attachment list shows alternating row colors and supports selection."""
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    assert window.preview_area.preview_list.alternatingRowColors() is True
    assert window.preview_area.preview_list.selectionMode() == QListWidget.SelectionMode.SingleSelection
    assert window.preview_area.preview_list.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_a_task_without_attachments_hides_the_attachment_list(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert window.preview_area.isHidden() is False
    assert window.preview_area.preview_list.isHidden() is True


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
    assert window.preview_area.preview_text.toPlainText() == ""


def test_a_closed_task_shows_the_archived_preview(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    # the folder is gone, so the text is read from inside the archive
    assert window.preview_area.isHidden() is False
    assert "# 18/09/2026" in window.preview_area.preview_text.toPlainText()


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
    assert window.preview_area.preview_text.toPlainText() == "# 18/09/2026\n\nChanged body\n"


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


# The titles of the two panels of the task preview.


def title_text(header):
    """The title the header of a preview panel carries."""
    return header.model().headerData(
        0, header.orientation(), Qt.ItemDataRole.DisplayRole
    )


def with_attachment(tmp_path, make_task):
    """A task carrying an attachment, so both panels are up."""
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    return file


def test_the_titles_name_the_two_panels(window, tmp_path, make_task):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert title_text(window.preview_area.preview_text_header) == "Details"
    assert title_text(window.preview_area.preview_list_header) == "Attachments"


def test_the_titles_appear_only_with_a_task_selected(window, tmp_path, make_task):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    assert window.preview_area.preview_text_header.isVisible() is False
    assert window.preview_area.preview_list_header.isVisible() is False

    select_task(window, file)

    assert window.preview_area.preview_text_header.isVisible() is True
    assert window.preview_area.preview_list_header.isVisible() is True


def test_without_attachments_only_the_details_title_is_shown(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert window.preview_area.preview_text_header.isVisible() is True
    assert window.preview_area.preview_list_header.isVisible() is False
    assert window.preview_area.preview_list_panel.isVisible() is False


def test_each_title_takes_the_height_of_the_directory_header(
    window, tmp_path, make_task
):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    select_task(window, file)

    height = directory_header(window).height()
    assert window.preview_area.preview_text_header.height() == height
    assert window.preview_area.preview_list_header.height() == height


def test_each_title_sits_at_the_top_of_its_panel_above_its_content(
    qtbot, window, tmp_path, make_task
):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    select_task(window, file)
    qtbot.wait(1)

    for header, content, panel in [
        (window.preview_area.preview_text_header, window.preview_area.preview_text, window.preview_area.preview_text_panel),
        (window.preview_area.preview_list_header, window.preview_area.preview_list, window.preview_area.preview_list_panel),
    ]:
        assert header.parent() is panel
        assert header.geometry().top() == 0
        assert header.geometry().bottom() <= content.geometry().top()


# The preview of a task read from inside its archive.


def closed_with_attachment(tmp_path, make_task):
    """Closes a task that carries one attachment, returning its archive."""
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    close_task(file.parent, "Foo")
    return tmp_path / "260918 - Foo.zip"


def test_a_closed_task_shows_its_body_and_the_archived_titles(window, tmp_path, make_task):
    archive = closed_with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, archive, "Closed")

    assert window.preview_area.isHidden() is False
    assert window.preview_area.preview_text.isReadOnly() is True
    assert "The body" in window.preview_area.preview_text.toPlainText()
    assert title_text(window.preview_area.preview_text_header) == "Details (archived)"
    assert title_text(window.preview_area.preview_list_header) == "Attachments"


def test_an_open_task_after_a_closed_one_restores_the_title(
    window, tmp_path, make_task
):
    archive = closed_with_attachment(tmp_path, make_task)
    file = make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")
    select_task(window, archive, "Closed")

    select_tab(window, "All")
    select_task(window, file)

    assert title_text(window.preview_area.preview_text_header) == "Details"


def test_a_closed_task_without_attachments_hides_the_attachments(
    qtbot, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")
    qtbot.wait(1)

    assert window.preview_area.isHidden() is False
    assert window.preview_area.preview_list_panel.isHidden() is True
    assert window.preview_area.preview_list.isHidden() is True
    assert window.preview_area.sizes()[1] == 0


def test_no_selection_hides_the_preview(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    assert window.preview_area.isHidden() is True


def test_double_clicking_an_attachment_opens_the_archive(
    window, tmp_path, make_task, monkeypatch
):
    archive = closed_with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")
    select_task(window, archive, "Closed")
    opened = []
    monkeypatch.setattr("mktsk.gui.window.helpers.open_file", opened.append)

    assert window.preview_area.preview_list.toolTip() == "Double-click opens the archive (.zip)"
    window.preview_area.preview_list.itemDoubleClicked.emit(window.preview_area.preview_list.item(0))

    assert opened == [archive]


def test_double_clicking_an_open_task_attachment_does_not_open_the_archive(
    window, tmp_path, make_task, monkeypatch
):
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)
    opened = []
    monkeypatch.setattr("mktsk.gui.window.helpers.open_file", opened.append)
    monkeypatch.setattr(
        "mktsk.gui.preview.QDesktopServices.openUrl", lambda url: True
    )

    window.preview_area.preview_list.itemDoubleClicked.emit(window.preview_area.preview_list.item(0))

    assert opened == []


def test_opening_archived_attachment_when_open_file_raises_oserror(
    window, tmp_path, make_task, monkeypatch
):
    """If helpers.open_file raises OSError for an archived attachment, a warning is shown."""
    archive = closed_with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")
    select_task(window, archive, "Closed")

    warnings = []

    def failing_open_file(path):
        raise OSError("permission denied")

    monkeypatch.setattr("mktsk.gui.window.helpers.open_file", failing_open_file)
    monkeypatch.setattr(
        "mktsk.gui.window.QMessageBox.warning", lambda *args: warnings.append(args[2])
    )

    window.preview_area.preview_list.itemDoubleClicked.emit(window.preview_area.preview_list.item(0))

    assert len(warnings) == 1
    assert "permission denied" in warnings[0]


def test_set_panel_title_with_none_model(window):
    """_set_panel_title handles a header with no model gracefully."""
    from PySide6.QtWidgets import QHeaderView

    from mktsk.gui.preview import _set_panel_title

    # Create a header without a model
    header = QHeaderView(Qt.Orientation.Horizontal)
    # Should not raise
    _set_panel_title(header, "Test Title")


def test_the_closed_action_bar_still_offers_only_reopen(
    window, tmp_path, make_task
):
    archive = closed_with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    bar = action_bar(window, archive, "Closed")

    assert [button for button in bar.buttons() if button.isVisible()] == [
        bar.resume_button
    ]


def test_archived_task_subfolders_show_with_trailing_slash(
    window, tmp_path, make_task
):
    """Archived task shows subfolders with trailing '/' like open tasks."""
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    (file.parent / "Attachments").mkdir()
    (file.parent / "Attachments" / "one.txt").write_text("x", encoding="utf-8")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    names = [
        window.preview_area.preview_list.item(index).text()
        for index in range(window.preview_area.preview_list.count())
    ]
    assert names == ["Attachments/"]
