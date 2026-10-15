"""The clip column, which shows the attachments a task carries."""

from PySide6.QtCore import QRect
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QStyle

from mktsk.gui.tasklist import (
    _COLUMN_PADDING,
    _ENTRY_ROLE,
    _ICON_SIZE,
    _column_widths,
)
from tests.gui_helpers import (
    click_heading,
    find_task,
    painted_texts,
    render_row,
    row_texts,
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
