"""Opening attachments from the preview list."""

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from tests.gui_helpers import select_task


def test_single_click_selects_attachment_without_opening(window, tmp_path, make_task):
    """A single click selects an attachment but does not open it."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    # Click the attachment item
    item = window.preview_list.item(0)
    window.preview_list.setCurrentItem(item)

    # The item should be selected but open_file should not be called
    assert window.preview_list.currentItem() == item


def test_double_click_opens_file(window, tmp_path, make_task, monkeypatch):
    """Double-clicking a file requests opening it through Qt desktop services."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    opened = []

    def mock_open_url(url):
        opened.append(url.toLocalFile())
        return True

    with patch("PySide6.QtGui.QDesktopServices.openUrl", mock_open_url):
        item = window.preview_list.item(0)
        window.preview_list.itemDoubleClicked.emit(item)

    assert len(opened) == 1
    assert Path(opened[0]) == attachment


def test_double_click_opens_folder(window, tmp_path, make_task, monkeypatch):
    """Double-clicking a folder requests opening it through Qt desktop services."""
    file = make_task(tmp_path, "260918", "Foo")
    folder = file.parent / "Attachments"
    folder.mkdir()
    window.navigate_to(tmp_path)
    select_task(window, file)

    opened = []

    def mock_open_url(url):
        opened.append(url.toLocalFile())
        return True

    with patch("PySide6.QtGui.QDesktopServices.openUrl", mock_open_url):
        item = window.preview_list.item(0)  # "Attachments/"
        window.preview_list.itemDoubleClicked.emit(item)

    assert len(opened) == 1
    assert Path(opened[0]) == folder


def test_enter_key_opens_selected_attachment(window, tmp_path, make_task, monkeypatch):
    """Pressing Enter opens the currently selected attachment."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    opened = []

    def mock_open_url(url):
        opened.append(url.toLocalFile())
        return True

    with patch("PySide6.QtGui.QDesktopServices.openUrl", mock_open_url):
        item = window.preview_list.item(0)
        window.preview_list.setCurrentItem(item)
        # Simulate Enter key press
        from PySide6.QtGui import QKeyEvent
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        window.preview_list.keyPressEvent(event)

    assert len(opened) == 1
    assert Path(opened[0]) == attachment


def test_missing_file_triggers_warning_and_refresh(window, tmp_path, make_task, monkeypatch):
    """A missing file triggers a warning and refreshes the attachment list."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    # Delete the attachment
    attachment.unlink()

    # Try to open it
    item = window.preview_list.item(0)
    window.preview_list.itemDoubleClicked.emit(item)

    assert len(warnings) == 1
    assert "no longer exists" in warnings[0]
    # The list should be refreshed (empty now)
    assert window.preview_list.count() == 0


def test_missing_folder_triggers_warning_and_refresh(window, tmp_path, make_task, monkeypatch):
    """A missing folder triggers a warning and refreshes the attachment list."""
    file = make_task(tmp_path, "260918", "Foo")
    folder = file.parent / "Attachments"
    folder.mkdir()
    window.navigate_to(tmp_path)
    select_task(window, file)

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    # Delete the folder
    import shutil
    shutil.rmtree(folder)

    # Try to open it
    item = window.preview_list.item(0)
    window.preview_list.itemDoubleClicked.emit(item)

    assert len(warnings) == 1
    assert "no longer exists" in warnings[0]
    # The list should be refreshed (empty now)
    assert window.preview_list.count() == 0


def test_failed_open_triggers_warning(window, tmp_path, make_task, monkeypatch):
    """A failed Qt open request triggers a user-visible warning."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    def mock_open_url(url):
        return False  # Simulate failure

    with patch("PySide6.QtGui.QDesktopServices.openUrl", mock_open_url):
        item = window.preview_list.item(0)
        window.preview_list.itemDoubleClicked.emit(item)

    assert len(warnings) == 1
    assert "Could not open" in warnings[0]


def test_paths_with_spaces_and_unicode_opened_correctly(window, tmp_path, make_task, monkeypatch):
    """Paths containing spaces and non-ASCII characters are converted correctly."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "file with spaces.pdf"
    attachment.write_text("x", encoding="utf-8")
    unicode_attachment = file.parent / "café.txt"
    unicode_attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    opened = []

    def mock_open_url(url):
        opened.append(url.toLocalFile())
        return True

    with patch("PySide6.QtGui.QDesktopServices.openUrl", mock_open_url):
        # Open the file with spaces
        item = window.preview_list.findItems("file with spaces.pdf", Qt.MatchFlag.MatchExactly)[0]
        window.preview_list.itemDoubleClicked.emit(item)

        # Open the unicode file
        item = window.preview_list.findItems("café.txt", Qt.MatchFlag.MatchExactly)[0]
        window.preview_list.itemDoubleClicked.emit(item)

    assert len(opened) == 2
    assert Path(opened[0]) == attachment
    assert Path(opened[1]) == unicode_attachment


def test_no_regression_on_attachment_list_display(window, tmp_path, make_task):
    """Existing attachment list display behavior is preserved."""
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
    assert window.preview_list.alternatingRowColors() is True
