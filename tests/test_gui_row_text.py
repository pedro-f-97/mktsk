"""The text of a row, inside its columns and clear of the action bar."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QLayout, QStyleOptionViewItem

from mktsk.gui.tasklist import TaskPanel
from tests.gui_helpers import find_task, select_task, task_listing, task_panel

LONG_TITLE = "ExtraordinarilyLongTaskTitleThatSurelyDoesNotFitInTheTaskColumn"
SHORT_TITLE = "Fix"
WIDTHS = (900, 500)


def _recording_paint(monkeypatch, rows):
    """Repaints a listing, recording every text the painting draws."""
    painted = []
    original = QPainter.drawText

    def record(painter, *args):
        if len(args) == 3 and isinstance(args[0], QRect):
            painted.append((QRect(args[0]), args[1], args[2], QFont(painter.font())))
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", record)
    rows.viewport().repaint()
    return painted


def _ink_rect(rect, flags, text, font):
    """The rectangle a painted text covers, from its alignment in its rect."""
    advance = QFontMetrics(font).horizontalAdvance(text)
    alignment = Qt.AlignmentFlag(flags & 0x000F)
    if alignment == Qt.AlignmentFlag.AlignHCenter:
        left = rect.left() + (rect.width() - advance) // 2
    elif alignment == Qt.AlignmentFlag.AlignRight:
        left = rect.left() + rect.width() - advance
    else:
        left = rect.left()

    return QRect(left, rect.top(), advance, rect.height())


def _row_texts(painted, row):
    """The texts painted on one row, in the order the delegate paints them."""
    return [
        (rect, flags, text, font)
        for rect, flags, text, font in painted
        if row.top() <= rect.top() < row.bottom()
    ]


def _style_text(rows, item):
    """The text the style is asked to paint on a row, empty for a task row.

    The four cells of a task row are painted by the delegate, so the option
    the style paints from carries no text and the whole row is what the cells
    draw. The base class fills that text on every paint, which is why the
    delegate empties it in `initStyleOption` rather than in `paint`.
    """
    option = QStyleOptionViewItem()
    index = rows.model().index(rows.row(item), 0)

    rows.delegate.initStyleOption(option, index)

    return option.text


def _at_width(qtbot, window, width):
    """Resizes the window, taking away the sizes that would hold it wider."""
    window.directory_tree.setMinimumWidth(0)
    window.tabs.setMinimumWidth(0)
    layout = window.layout()
    if layout is not None:
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
    for index in range(window.tabs.count()):
        panel = window.tabs.widget(index)
        if isinstance(panel, TaskPanel):
            panel.header.setMinimumWidth(0)
            panel.listing.setMinimumWidth(0)
    window.setMinimumSize(0, 0)
    window.resize(width, 600)
    qtbot.wait(1)

    assert window.width() == width


def test_the_columns_of_a_row_start_where_the_headings_start(
    window, tmp_path, make_task
):
    long_file = make_task(tmp_path, "260918", LONG_TITLE)
    short_file = make_task(tmp_path, "260919", SHORT_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header

    for file in (long_file, short_file):
        item = find_task(window, file)
        row = QRect(rows.visualItemRect(item))
        cells = [rows.column_rect(row, column) for column in range(4)]

        for column, cell in enumerate(cells):
            assert cell.left() == header.sectionPosition(column)
            assert cell.width() == header.sectionSize(column)

        for left in range(4):
            for right in range(left + 1, 4):
                assert not cells[left].intersects(cells[right])


def test_the_painted_text_of_every_column_fits_its_rectangle(
    monkeypatch, window, tmp_path, make_task
):
    long_file = make_task(tmp_path, "260918", LONG_TITLE)
    short_file = make_task(tmp_path, "260919", SHORT_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)

    painted = _recording_paint(monkeypatch, rows)
    for file in (long_file, short_file):
        item = find_task(window, file)
        row = QRect(rows.visualItemRect(item))
        texts = _row_texts(painted, row)

        assert _style_text(rows, item) == ""
        assert len(texts) == 4
        for column, (rect, flags, text, font) in enumerate(texts):
            assert rows.column_rect(row, column).contains(
                _ink_rect(rect, flags, text, font)
            )


def test_a_task_row_leaves_no_text_for_the_style(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", LONG_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)

    assert _style_text(rows, find_task(window, file)) == ""


def test_a_heading_row_keeps_its_text_for_the_style(window, tmp_path, make_task):
    make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    heading = rows.item(0)

    assert heading.text() != ""
    assert _style_text(rows, heading) == heading.text()


def test_the_action_bar_keeps_clear_of_the_painted_text(
    monkeypatch, qtbot, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", LONG_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)

    for width in WIDTHS:
        _at_width(qtbot, window, width)
        painted = _recording_paint(monkeypatch, listing)
        row = QRect(listing.visualItemRect(listing.currentItem()))
        bar = QRect(listing.action_bar.geometry())
        viewport = listing.viewport()

        assert listing.action_bar.isVisible()
        assert _style_text(listing, listing.currentItem()) == ""
        assert bar.left() >= 0
        assert bar.right() < viewport.width()
        assert bar.bottom() < viewport.height()
        for rect, flags, text, font in _row_texts(painted, row):
            assert not bar.intersects(_ink_rect(rect, flags, text, font))
