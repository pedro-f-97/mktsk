"""The text of a row, inside its columns and clear of the action bar."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPalette
from PySide6.QtWidgets import QLayout, QStyle, QStyleOptionViewItem

from mktsk.gui.tasklist import TaskPanel, _cell_pen, _contrast_ratio
from tests.gui_helpers import (
    find_directory,
    find_task,
    select_task,
    task_listing,
    task_panel,
)

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


_SELECTED_ACTIVE = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
_SELECTED_INACTIVE = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Selected
_UNSELECTED = QStyle.StateFlag.State_Enabled

# the contrast WCAG AA asks of body text
_MINIMUM_CONTRAST = 4.5


def _render_row(view, item, state, background):
    """Renders one task or folder row offscreen, over a given background.

    The row is painted the way the view paints it: the option is filled from
    the item, the state is the one a selected or unselected row carries, and
    the palette is the one of the viewport. The style paints the row
    background and the delegate paints the cells, so the image holds what a
    person sees.
    """
    rect = QRect(view.visualItemRect(item))
    image = QImage(rect.size(), QImage.Format.Format_RGB32)
    image.fill(background)
    index = view.indexFromItem(item)
    delegate = view.itemDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, index)
    option.rect = QRect(0, 0, rect.width(), rect.height())
    option.state = state
    option.palette = view.viewport().palette()
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()
    return image


def _painted_colours(image):
    """Counts the colours of a row from its pixels, the most painted first."""
    counts: dict[int, int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            key = image.pixelColor(x, y).rgb()
            counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda pair: -pair[1])


def _contrast(view, item, state):
    """The text colour, the background colour and the contrast of a row.

    The background is the colour the row is mostly made of, and the text is
    the next one: the delegate draws its four cells in a single colour, so
    every other pixel of the row is an edge of that text.
    """
    base = view.viewport().palette().color(QPalette.ColorRole.Base)
    painted = _painted_colours(_render_row(view, item, state, base))
    background = QColor(painted[0][0])
    text = QColor(painted[1][0])
    return text, background, _contrast_ratio(text, background)


def _readable(view, item, state):
    text, background, ratio = _contrast(view, item, state)
    assert ratio >= _MINIMUM_CONTRAST, f"{text.name()} on {background.name()}: {ratio}"


def test_a_selected_task_row_paints_readable_text(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        _readable(listing, item, state)


def test_an_unselected_task_row_paints_readable_text(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    _readable(listing, item, _UNSELECTED)


def test_an_unselected_folder_row_paints_readable_text(window, tmp_path):
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    _readable(tree, item, _UNSELECTED)


def test_a_disabled_cell_reads_its_pen_from_the_disabled_group():
    palette = QPalette()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor("#eeeeee"))
        palette.setColor(group, QPalette.ColorRole.HighlightedText, QColor("#eeeeee"))
        palette.setColor(group, QPalette.ColorRole.Text, QColor("#eeeeee"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor("#ffffff")
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        QColor("#000000"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#fefefe")
    )
    option = QStyleOptionViewItem()
    # a lack of State_Enabled is what makes a row disabled
    option.state = QStyle.StateFlag.State_Selected
    option.palette = palette

    assert _cell_pen(option) == QColor("#000000")


def test_a_selected_row_keeps_its_cells_inside_their_columns(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", LONG_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)

    painted = _recording_paint(monkeypatch, listing)
    row = QRect(listing.visualItemRect(listing.currentItem()))

    for column, (rect, flags, text, font) in enumerate(_row_texts(painted, row)):
        assert listing.column_rect(row, column).contains(
            _ink_rect(rect, flags, text, font)
        )
