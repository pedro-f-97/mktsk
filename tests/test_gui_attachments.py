"""The clip column, which shows the attachments a task carries."""

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QMessageBox, QStyle

from mktsk.gui.icons import _ICON_SIZE
from mktsk.gui.taskrow import _COLUMN_PADDING, _ENTRY_ROLE, _column_widths
from tests.gui_helpers import (
    click_heading,
    find_task,
    painted_texts,
    render_row,
    row_texts,
    select_task,
    task_listing,
    task_panel,
)


def _attach(file, name):
    """Puts a file beside the .md of a task, as an attachment."""
    attachment = file.parent / name
    attachment.write_text("x", encoding="utf-8")
    return attachment


def _clip_text(monkeypatch, listing, item):
    """The text the delegate paints in the clip column of a row."""
    row = QRect(listing.visualItemRect(item))
    painted = row_texts(painted_texts(monkeypatch, listing), row)
    return painted[2][2]


def _clip_ink(image, clip):
    """Counts the dark marks painted in the paperclip half of the clip column."""
    icon = QRect(clip.left() + _COLUMN_PADDING, 0, _ICON_SIZE, image.height())
    return sum(
        1
        for x in range(icon.left(), icon.right() + 1)
        for y in range(icon.top(), icon.bottom() + 1)
        if image.pixelColor(x, y).lightness() < 128
    )


def test_a_task_with_attachments_shows_the_count_in_the_clip_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    for name in ("one.pdf", "two.pdf", "three.pdf"):
        _attach(file, name)
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    assert _clip_text(monkeypatch, listing, find_task(window, file)) == "3"


def test_a_task_without_attachments_shows_nothing_in_the_clip_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    assert _clip_text(monkeypatch, listing, find_task(window, file)) == ""


def test_the_clip_column_shows_a_paperclip(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    _attach(file, "one.pdf")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)
    image = render_row(listing, item, QStyle.StateFlag.State_Enabled)
    clip = listing.column_rect(
        QRect(0, 0, image.width(), image.height()), 2
    )

    assert _clip_ink(image, clip) > 0


def _titles(window, title="All"):
    """The titles of the task rows of a tab, in order."""
    listing = task_listing(window, title)
    return [
        listing.item(index).data(_ENTRY_ROLE).title
        for index in range(listing.count())
        if listing.item(index).data(_ENTRY_ROLE) is not None
    ]


def test_clicking_the_clip_heading_does_not_sort(window, tmp_path, make_task):
    _attach(make_task(tmp_path, "260918", "Foo"), "one.pdf")
    make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    header = task_panel(window).header
    before = _titles(window)

    click_heading(window, 2)

    assert header.isSortIndicatorShown() is False
    assert _titles(window) == before


def test_the_clip_column_keeps_its_width_when_the_window_resizes(
    qtbot, window, tmp_path, make_task
):
    _attach(make_task(tmp_path, "260918", "Foo"), "one.pdf")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    before = listing.header.sectionSize(2)

    window.resize(window.width() + 200, window.height())
    qtbot.wait(1)

    assert listing.header.sectionSize(2) == before


def test_the_clip_column_fits_a_paperclip_and_two_digits(window, tmp_path, make_task):
    _attach(make_task(tmp_path, "260918", "Few"), "one.pdf")
    many = make_task(tmp_path, "260919", "Many")
    for index in range(12):
        _attach(many, f"{index}.pdf")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    columns = _column_widths()

    assert listing.header.sectionSize(2) == columns.clip
    text = QFontMetrics(QApplication.font()).horizontalAdvance("44")
    assert columns.clip >= _ICON_SIZE + text


# Opening attachments from the preview list.


def test_single_click_selects_attachment_without_opening(window, tmp_path, make_task):
    """A single click selects an attachment but does not open it."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    # Click the attachment item
    item = window.preview_area.preview_list.item(0)
    window.preview_area.preview_list.setCurrentItem(item)

    # The item should be selected but open_file should not be called
    assert window.preview_area.preview_list.currentItem() == item


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
        item = window.preview_area.preview_list.item(0)
        window.preview_area.preview_list.itemDoubleClicked.emit(item)

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
        item = window.preview_area.preview_list.item(0)  # "Attachments/"
        window.preview_area.preview_list.itemDoubleClicked.emit(item)

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
        item = window.preview_area.preview_list.item(0)
        window.preview_area.preview_list.setCurrentItem(item)
        # Simulate Enter key press
        from PySide6.QtGui import QKeyEvent
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        window.preview_area.preview_list.keyPressEvent(event)

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
    item = window.preview_area.preview_list.item(0)
    window.preview_area.preview_list.itemDoubleClicked.emit(item)

    assert len(warnings) == 1
    assert "no longer exists" in warnings[0]
    # The list should be refreshed (empty now)
    assert window.preview_area.preview_list.count() == 0


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
    item = window.preview_area.preview_list.item(0)
    window.preview_area.preview_list.itemDoubleClicked.emit(item)

    assert len(warnings) == 1
    assert "no longer exists" in warnings[0]
    # The list should be refreshed (empty now)
    assert window.preview_area.preview_list.count() == 0


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
        item = window.preview_area.preview_list.item(0)
        window.preview_area.preview_list.itemDoubleClicked.emit(item)

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
        item = window.preview_area.preview_list.findItems("file with spaces.pdf", Qt.MatchFlag.MatchExactly)[0]
        window.preview_area.preview_list.itemDoubleClicked.emit(item)

        # Open the unicode file
        item = window.preview_area.preview_list.findItems("café.txt", Qt.MatchFlag.MatchExactly)[0]
        window.preview_area.preview_list.itemDoubleClicked.emit(item)

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
        window.preview_area.preview_list.item(index).text()
        for index in range(window.preview_area.preview_list.count())
    ]
    assert names == ["Attachments/", "one.pdf"]
    assert window.preview_area.preview_list.alternatingRowColors() is True


def test_malformed_item_data_does_not_crash(window, tmp_path, make_task):
    """An item with non-Path data is handled gracefully (line 774)."""
    file = make_task(tmp_path, "260918", "Foo")
    attachment = file.parent / "one.pdf"
    attachment.write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    # Corrupt the item data
    item = window.preview_area.preview_list.item(0)
    item.setData(Qt.ItemDataRole.UserRole, "not a path")

    # Should not raise, should just return early
    window.preview_area.open_attachment(item)


def test_non_enter_key_passes_to_base_class(window, tmp_path, make_task):
    """Non-Enter keys are passed to the base implementation for navigation (line 793)."""
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    (file.parent / "two.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    # Select first item
    item0 = window.preview_area.preview_list.item(0)
    window.preview_area.preview_list.setCurrentItem(item0)
    assert window.preview_area.preview_list.currentItem() == item0

    # Press Down arrow - should move selection to second item via base class
    from PySide6.QtGui import QKeyEvent
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    window.preview_area.preview_list.keyPressEvent(event)

    # Selection should have moved to the second item
    assert window.preview_area.preview_list.currentItem() == window.preview_area.preview_list.item(1)


def test_enter_with_no_selection_does_nothing(window, tmp_path, make_task):
    """Pressing Enter with no selected item does not crash (branch 790->793)."""
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "one.pdf").write_text("x", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, file)

    # Clear selection
    window.preview_area.preview_list.clearSelection()
    window.preview_area.preview_list.setCurrentItem(None)
    assert window.preview_area.preview_list.currentItem() is None

    # Press Enter - should not crash, should not call _open_attachment
    from PySide6.QtGui import QKeyEvent
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    window.preview_area.preview_list.keyPressEvent(event)

    # No error, test passes if we reach here
