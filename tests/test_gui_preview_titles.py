"""The titles of the two panels of the task preview."""

from PySide6.QtCore import Qt

from tests.gui_helpers import directory_header, select_task


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

    assert title_text(window.preview_text_header) == "Details"
    assert title_text(window.preview_list_header) == "Attachments"


def test_the_titles_appear_only_with_a_task_selected(window, tmp_path, make_task):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    assert window.preview_text_header.isVisible() is False
    assert window.preview_list_header.isVisible() is False

    select_task(window, file)

    assert window.preview_text_header.isVisible() is True
    assert window.preview_list_header.isVisible() is True


def test_without_attachments_only_the_details_title_is_shown(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    select_task(window, file)

    assert window.preview_text_header.isVisible() is True
    assert window.preview_list_header.isVisible() is False
    assert window.preview_list_panel.isVisible() is False


def test_each_title_takes_the_height_of_the_directory_header(
    window, tmp_path, make_task
):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    select_task(window, file)

    height = directory_header(window).height()
    assert window.preview_text_header.height() == height
    assert window.preview_list_header.height() == height


def test_each_title_sits_at_the_top_of_its_panel_above_its_content(
    qtbot, window, tmp_path, make_task
):
    file = with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)

    select_task(window, file)
    qtbot.wait(1)

    for header, content, panel in [
        (window.preview_text_header, window.preview_text, window.preview_text_panel),
        (window.preview_list_header, window.preview_list, window.preview_list_panel),
    ]:
        assert header.parent() is panel
        assert header.geometry().top() == 0
        assert header.geometry().bottom() <= content.geometry().top()
