"""The preview of a task read from inside its archive."""

from PySide6.QtCore import Qt

from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab, select_task


def title_text(header):
    """The title the header of a preview panel carries."""
    return header.model().headerData(
        0, header.orientation(), Qt.ItemDataRole.DisplayRole
    )


def closed_with_attachment(tmp_path, make_task):
    """Closes a task that carries one attachment, returning its archive."""
    file = make_task(tmp_path, "260918", "Foo")
    file.write_text("# 18/09/2026\n\nThe body\n", encoding="utf-8")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    close_task(file.parent, "Foo")
    return tmp_path / "260918 - Foo.zip"


def test_a_closed_task_shows_the_archived_preview(window, tmp_path, make_task):
    archive = closed_with_attachment(tmp_path, make_task)
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    select_task(window, archive, "Closed")

    assert window.preview_area.isHidden() is False
    assert window.preview_text.isReadOnly() is True
    assert "The body" in window.preview_text.toPlainText()
    assert title_text(window.preview_text_header) == "Details (archived)"
    assert title_text(window.preview_list_header) == "Attachments"


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

    assert title_text(window.preview_text_header) == "Details"


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
    assert window.preview_list_panel.isHidden() is True
    assert window.preview_list.isHidden() is True
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

    assert window.preview_list.toolTip() == "Double-click opens the archive (.zip)"
    window.preview_list.itemDoubleClicked.emit(window.preview_list.item(0))

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
        "mktsk.gui.window.QDesktopServices.openUrl", lambda url: True
    )

    window.preview_list.itemDoubleClicked.emit(window.preview_list.item(0))

    assert opened == []


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
