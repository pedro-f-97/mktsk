"""The text of a row, inside its columns and clear of the action bar."""

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPalette
from PySide6.QtWidgets import (
    QLayout,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionViewItem,
)

from mktsk.gui import tasklist
from mktsk.gui.tasklist import (
    _AGE_ROLE,
    _SELECTION_INDICATOR_GAP,
    TaskPanel,
    _cell_pen,
    _contrast_ratio,
)
from tests.gui_helpers import (
    find_directory,
    find_task,
    painted_texts,
    row_texts,
    select_task,
    task_listing,
    task_panel,
)

LONG_TITLE = "ExtraordinarilyLongTaskTitleThatSurelyDoesNotFitInTheTaskColumn"
SHORT_TITLE = "Fix"
WIDTHS = (900, 500)


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


def _style_text(rows, item):
    """The text the style is asked to paint on a row, empty for a task row.

    The cells of a task row are painted by the delegate, so the option
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
        cells = [rows.column_rect(row, column) for column in range(6)]

        for column, cell in enumerate(cells):
            assert cell.left() == header.sectionPosition(column)
            assert cell.width() == header.sectionSize(column)

        for left in range(6):
            for right in range(left + 1, 6):
                assert not cells[left].intersects(cells[right])


def test_the_painted_text_of_every_column_fits_its_rectangle(
    monkeypatch, window, tmp_path, make_task
):
    long_file = make_task(tmp_path, "260918", LONG_TITLE)
    short_file = make_task(tmp_path, "260919", SHORT_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)

    painted = painted_texts(monkeypatch, rows)
    for file in (long_file, short_file):
        item = find_task(window, file)
        row = QRect(rows.visualItemRect(item))
        texts = row_texts(painted, row)

        assert _style_text(rows, item) == ""
        assert len(texts) == 6
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
        painted = painted_texts(monkeypatch, listing)
        row = QRect(listing.visualItemRect(listing.currentItem()))
        bar = QRect(listing.action_bar.geometry())
        viewport = listing.viewport()

        assert listing.action_bar.isVisible()
        assert _style_text(listing, listing.currentItem()) == ""
        assert bar.left() >= 0
        assert bar.right() < viewport.width()
        assert bar.bottom() < viewport.height()
        for rect, flags, text, font in row_texts(painted, row):
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

# the room the ink of the first glyph may keep past the padding the date
# text is drawn from: its left bearing, which the platform's smoothing of
# the glyphs may push a pixel or two further
_MAX_GLYPH_BEARING = 4


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
    option.widget = view
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


def _ink_contrast(view, item, state):
    """The ink colour of a row, the background colour and their contrast.

    The ink is the pixel that stands furthest from the background among the
    columns the cells are painted in, leaving the rail at the left edge out.
    The cells are drawn in a single colour, but a platform that smooths its
    glyphs blends them with the background, so the furthest shade still
    carries the text where the most painted colours would name the rail.
    """
    base = view.viewport().palette().color(QPalette.ColorRole.Base)
    image = _render_row(view, item, state, base)
    painted = _painted_colours(image)
    background = QColor(painted[0][0])
    ink = max(
        (
            image.pixelColor(x, y)
            for x in range(tasklist._SELECTION_INDICATOR_WIDTH, image.width())
            for y in range(image.height())
        ),
        key=lambda colour: _contrast_ratio(colour, background),
    )
    return ink, background, _contrast_ratio(ink, background)


def _readable_ink(view, item, state):
    """Asserts the ink of a row reads against its background, smoothed or not."""
    ink, background, ratio = _ink_contrast(view, item, state)
    assert ratio >= _MINIMUM_CONTRAST, f"{ink.name()} on {background.name()}: {ratio}"


# the styles the environment offers, so a row is rendered under each of them
_STYLES = tuple(QStyleFactory.keys())


def _restore_style(qapp, name):
    """Puts back the style the application had, by name.

    The application owns the style it is given and deletes the one it had, so
    the old style is remembered by name rather than kept as a dangling object.
    """
    style = QStyleFactory.create(name)
    if style is not None:
        qapp.setStyle(style)


@pytest.fixture(params=_STYLES)
def styled(request, qapp):
    """Sets a style on the application for one test and puts the old one back."""
    original = qapp.style().objectName()
    style = QStyleFactory.create(request.param)
    if style is None:
        pytest.skip(f"{request.param} cannot be created")
    qapp.setStyle(style)
    yield request.param
    _restore_style(qapp, original)


def _background_pixel(image):
    """The colour most of a row is made of, which is its background."""
    return QColor(_painted_colours(image)[0][0])


def _glyph_colour(image, background):
    """The pixel of a row that stands furthest from its background.

    The body of a glyph is the colour the row was drawn in; its edges are
    shades between that colour and the background, so the furthest pixel is
    the one the text is made of.
    """
    furthest = background
    best = 0.0
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            ratio = _contrast_ratio(colour, background)
            if ratio > best:
                best = ratio
                furthest = colour
    return furthest


def _rendered_contrast(view, item, state):
    """The rendered text, background and contrast of a row.

    The row is rendered the way the view paints it and read back from its
    pixels, so what is measured is what a person sees rather than what the
    palette says.
    """
    base = view.viewport().palette().color(QPalette.ColorRole.Base)
    image = _render_row(view, item, state, base)
    background = _background_pixel(image)
    text = _glyph_colour(image, background)
    return text, background, _contrast_ratio(text, background)


def _rendered_readable(view, item, state):
    text, background, ratio = _rendered_contrast(view, item, state)
    assert ratio >= _MINIMUM_CONTRAST, f"{text.name()} on {background.name()}: {ratio}"


# the fills a style of its own may paint: one light, where the palette would
# choose a light text, and one dark, where it would choose a dark one
_FILLS = (("light", QColor("#f5f5f5")), ("dark", QColor("#1a1a1a")))


class _FilledSelectionStyle(QProxyStyle):
    """A style that paints a selection fill the palette does not describe.

    Some platform styles fill a selected row with a colour the palette knows
    nothing about, which would leave a text of the colour the palette chose on
    a background it was not chosen for. The proxy reproduces one, answering
    both the panel and the control with the same fill, so the row is painted
    the way such a style paints it and the pen has to be read back from the
    row rather than taken from the palette.
    """

    def __init__(self, base, colour):
        super().__init__(base)
        self.colour = colour

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            painter.fillRect(option.rect, self.colour)
            return
        super().drawControl(element, option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_PanelItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            painter.fillRect(option.rect, self.colour)
            return
        super().drawPrimitive(element, option, painter, widget)


@pytest.fixture(params=_FILLS, ids=[name for name, _ in _FILLS])
def filled_selection_style(qapp, request):
    """Puts a style that paints its own selection fill on the application.

    The palette is set against the fill the style paints, so the text the
    palette alone would choose is the wrong one: light on a light fill, dark
    on a dark one. Reading the fill back is the only way left to a readable
    text.
    """
    name, colour = request.param
    style_name = qapp.style().objectName()
    original_palette = qapp.palette()
    style = _FilledSelectionStyle(QStyleFactory.create(style_name), colour)
    style.setObjectName(name)
    qapp.setStyle(style)
    palette = qapp.palette()
    if name == "light":
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#0067c0"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
    else:
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    qapp.setPalette(palette)
    yield style
    _restore_style(qapp, style_name)
    qapp.setPalette(original_palette)


class _NoSelectionStyle(QProxyStyle):
    """A style that paints no selection of its own.

    A style that draws nothing for a selected row leaves the row over the base
    colour of the viewport, which is whatever the selection has to be read
    against.
    """

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            return
        super().drawControl(element, option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_PanelItemViewItem and (
            option.state & QStyle.StateFlag.State_Selected
        ):
            return
        super().drawPrimitive(element, option, painter, widget)


@pytest.fixture
def no_selection_style(qapp):
    """Puts a style that paints no selection on the application."""
    style_name = qapp.style().objectName()
    qapp.setStyle(_NoSelectionStyle(QStyleFactory.create(style_name)))
    yield
    _restore_style(qapp, style_name)


class _RecordingStyle(QProxyStyle):
    """A style that keeps the state of every row it paints."""

    def __init__(self, base):
        super().__init__(base)
        self.states = []

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem:
            self.states.append(option.state)
        super().drawControl(element, option, painter, widget)


@pytest.fixture
def recording_style(qapp):
    """Puts a style on the application that records what it is asked to paint."""
    style_name = qapp.style().objectName()
    style = _RecordingStyle(QStyleFactory.create(style_name))
    qapp.setStyle(style)
    yield style
    _restore_style(qapp, style_name)


def test_a_selected_task_row_renders_readable_text_in_every_style(
    styled, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        _rendered_readable(listing, item, state)


def test_an_unselected_task_row_renders_readable_text_in_every_style(
    styled, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    _rendered_readable(listing, item, _UNSELECTED)


def test_an_unselected_folder_row_renders_readable_text_in_every_style(
    styled, window, tmp_path
):
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    _rendered_readable(tree, item, _UNSELECTED)


def test_a_selection_the_style_paints_itself_stays_readable(
    filled_selection_style, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        _rendered_readable(listing, item, state)


def test_a_selected_row_is_tinted_even_when_the_style_paints_no_selection(
    no_selection_style, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)
    base = listing.viewport().palette().color(QPalette.ColorRole.Base)

    # the selection is the delegate's, so it reaches the pixels whether the
    # style paints one of its own or paints nothing at all
    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        tint = tasklist._selection_tint(_row_option(listing, item, state))
        assert _background_pixel(_render_row(listing, item, state, base)) == tint


def test_the_option_handled_to_the_style_keeps_the_selection(
    recording_style, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)
    base = listing.viewport().palette().color(QPalette.ColorRole.Base)

    # the window has already painted its tree and its list, so what matters
    # is the row this test renders rather than the rows that came before it
    recording_style.states.clear()
    _render_row(listing, item, _SELECTED_ACTIVE, base)

    assert recording_style.states
    for state in recording_style.states:
        assert state & QStyle.StateFlag.State_Selected


def test_the_auxiliary_band_of_a_selected_row_carries_the_selection(
    filled_selection_style, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = find_task(window, file)
    base = listing.viewport().palette().color(QPalette.ColorRole.Base)
    selected = _render_row(listing, item, _SELECTED_ACTIVE, base)
    option = _row_option(listing, item, _SELECTED_ACTIVE)
    tint = tasklist._selection_tint(option)
    highlight = option.palette.color(QPalette.ColorRole.Highlight)

    # the delegate paints its own selection over the style's, so the band
    # carries the tint from the rail to the right edge on every row of it,
    # the rail itself rounding off at its bottom end, and no cell of the row
    # is painted past the room it keeps above the band. The last rows of the
    # row hold the bottom line instead: the accent over the arm of the line
    # and the tint past it
    band_top = listing.delegate.min_height
    line_height = tasklist._SELECTION_INDICATOR_WIDTH
    arm = line_height + tasklist._ROW_LINE_REACH
    assert selected.height() > band_top
    for y in range(band_top, selected.height() - line_height):
        assert {selected.pixelColor(x, y).rgb() for x in range(line_height, selected.width())} == {tint.rgb()}
    for y in range(selected.height() - line_height, selected.height()):
        assert {selected.pixelColor(x, y).rgb() for x in range(line_height, arm)} == {highlight.rgb()}
        assert {selected.pixelColor(x, y).rgb() for x in range(arm, selected.width())} == {tint.rgb()}
    assert {selected.pixelColor(x, band_top + 2).rgb() for x in range(line_height)} == {highlight.rgb()}
    assert all(
        selected.pixelColor(x, y) != filled_selection_style.colour
        for y in range(band_top, selected.height())
        for x in range(selected.width())
    )


def test_a_selected_task_row_paints_readable_text(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    for state in (_SELECTED_ACTIVE, _SELECTED_INACTIVE):
        _readable_ink(listing, item, state)


def test_an_unselected_task_row_paints_readable_text(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    item = find_task(window, file)

    _readable_ink(listing, item, _UNSELECTED)


def test_an_unselected_folder_row_paints_readable_text(window, tmp_path):
    (tmp_path / "Reports").mkdir()
    window.navigate_to(tmp_path)
    tree = window.directory_tree
    item = find_directory(window, tmp_path / "Reports")

    _readable(tree, item, _UNSELECTED)


def test_a_disabled_cell_reads_its_pen_from_the_disabled_group():
    palette = QPalette()
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor("#ffffff")
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

    highlighted = QColor("#000000")
    plain = QColor("#fefefe")
    tint = tasklist._selection_tint(option)
    expected = (
        plain
        if _contrast_ratio(plain, tint) > _contrast_ratio(highlighted, tint)
        else highlighted
    )
    assert _cell_pen(option) == expected


def test_the_cells_of_an_unselected_row_stay_inside_their_columns(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", LONG_TITLE)
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))

    painted = row_texts(painted_texts(monkeypatch, rows), row)
    cells = [rows.column_rect(row, column) for column in range(6)]

    for column, (rect, flags, text, font) in enumerate(painted):
        assert cells[column].contains(_ink_rect(rect, flags, text, font))
    for left in range(6):
        for right in range(left + 1, 6):
            assert not cells[left].intersects(cells[right])


def test_a_selected_row_shifts_its_cells_and_leaves_the_others(
    monkeypatch, window, tmp_path, make_task
):
    selected_file = make_task(tmp_path, "260918", SHORT_TITLE)
    other_file = make_task(tmp_path, "260919", LONG_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, selected_file)
    padding = listing.header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)

    painted = painted_texts(monkeypatch, listing)
    selected_row = QRect(listing.visualItemRect(find_task(window, selected_file)))
    other_row = QRect(listing.visualItemRect(find_task(window, other_file)))
    selected = row_texts(painted, selected_row)
    other = row_texts(painted, other_row)

    from mktsk.gui import tasklist
    assert (
        selected[0][0].left()
        == listing.column_rect(selected_row, 0).left() + max(padding, tasklist._DATE_TEXT_LEFT_PADDING)
    )
    for column in range(1, 6):
        assert (
            selected[column][0].left()
            == listing.column_rect(selected_row, column).left()
        )
    from mktsk.gui import tasklist
    assert other[0][0].left() == listing.column_rect(other_row, 0).left() + max(padding, tasklist._DATE_TEXT_LEFT_PADDING)
    for column in range(1, 6):
        assert (
            other[column][0].left() == listing.column_rect(other_row, column).left()
        )


def _painted_row(monkeypatch, rows, item, width):
    """Paints one selected row at a chosen width, recording every text drawn."""
    painted = []
    original = QPainter.drawText

    def record(painter, *args):
        if len(args) == 3 and isinstance(args[0], QRect):
            painted.append((QRect(args[0]), args[1], args[2], QFont(painter.font())))
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", record)
    index = rows.indexFromItem(item)
    option = QStyleOptionViewItem()
    rows.delegate.initStyleOption(option, index)
    row = QRect(0, 0, width, rows.delegate.min_height)
    option.rect = QRect(row)
    option.state = _SELECTED_ACTIVE
    option.palette = rows.viewport().palette()
    option.widget = rows
    image = QImage(row.size(), QImage.Format.Format_RGB32)
    image.fill(rows.viewport().palette().color(QPalette.ColorRole.Base))
    painter = QPainter(image)
    rows.delegate.paint(painter, option, index)
    painter.end()
    return painted, row


def test_a_selected_row_elides_at_the_cut_edge(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", LONG_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = listing.currentItem()
    full = QRect(0, 0, listing.header.length(), listing.delegate.min_height)
    activity = listing.column_rect(full, 5)
    advance = QFontMetrics(listing.font()).horizontalAdvance(item.data(_AGE_ROLE))
    # paint at a width that really cuts the age cell
    visible = min(advance - 2, activity.width() - 1)
    width = activity.left() + visible

    painted, row = _painted_row(monkeypatch, listing, item, width)
    texts = row_texts(painted, row)

    assert visible > 0
    fm = QFontMetrics(listing.font())
    age_text = texts[5][2] if len(texts) > 5 else item.data(_AGE_ROLE)
    assert age_text != item.data(_AGE_ROLE)
    assert fm.horizontalAdvance(age_text) <= visible
    for rect, flags, text, font in texts:
        if not text or not row.intersects(rect):
            continue
        ink = _ink_rect(rect, flags, text, font)
        assert row.contains(ink), (
            f"ink fora da row: row={row} ink={ink} "
            f"cell={rect} text={text!r} font={font.family()!r} "
            f"dy_top={row.top() - ink.top()} dy_bottom={ink.bottom() - row.bottom()}"
        )
        assert row.left() <= rect.left() + rect.width() <= row.right() + 1


def _row_option(view, item, state):
    """The option a row is rendered from, built the way `_render_row` builds it."""
    rect = QRect(view.visualItemRect(item))
    index = view.indexFromItem(item)
    option = QStyleOptionViewItem()
    view.itemDelegate().initStyleOption(option, index)
    option.rect = QRect(0, 0, rect.width(), rect.height())
    option.state = state
    option.palette = view.viewport().palette()
    option.widget = view
    return option


def _columns_of_colour(image, colour, rows=None):
    """The x positions of a row that hold at least one pixel of a colour."""
    rows = rows if rows is not None else range(image.height())
    return [
        x
        for x in range(image.width())
        if any(image.pixelColor(x, y) == colour for y in rows)
    ]


def _rail_columns(image, colour):
    """The x positions the indicator rail of a selected row holds a colour at.

    The rows the top and bottom lines paint are left out of the scan: those
    rows hold the colour across the arm of the lines rather than only at the
    rail.
    """
    thickness = tasklist._SELECTION_INDICATOR_WIDTH
    rows = range(thickness, image.height() - thickness)
    return _columns_of_colour(image, colour, rows)


def _first_glyph_x(image, pen, start=0):
    """The x of the leftmost pixel painted in the pen of the text."""
    for x in range(start, image.width()):
        if any(image.pixelColor(x, y) == pen for y in range(image.height())):
            return x

    raise AssertionError("no glyph was painted on the row")


def _first_ink_x(image, background):
    """The x of the leftmost pixel that stands at a text contrast to a background.

    The cells are drawn in a single colour, but a platform that smooths its
    glyphs blends them with the background, so the ink is read as the first
    column holding a pixel at the body-text contrast rather than a pixel of
    the exact pen colour.
    """
    for x in range(image.width()):
        if any(
            _contrast_ratio(image.pixelColor(x, y), background) >= _MINIMUM_CONTRAST
            for y in range(image.height())
        ):
            return x

    raise AssertionError("no glyph was painted on the row")


def test_a_selected_row_keeps_the_indicator_at_the_left_edge(
    styled, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = listing.currentItem()
    palette = listing.viewport().palette()
    base = palette.color(QPalette.ColorRole.Base)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    padding = listing.header.style().pixelMetric(
        QStyle.PixelMetric.PM_HeaderMargin
    )

    image = _render_row(listing, item, _SELECTED_ACTIVE, base)
    indicator = _rail_columns(image, highlight)

    assert indicator == list(range(tasklist._SELECTION_INDICATOR_WIDTH))
    expected = max(padding, tasklist._DATE_TEXT_LEFT_PADDING)
    first_ink = _first_ink_x(image, _background_pixel(image))
    # the text starts on the padding the date is drawn from, give or take
    # the left bearing of its first glyph, which the smoothing may extend
    assert expected <= first_ink <= expected + _MAX_GLYPH_BEARING


def test_a_selected_row_keeps_the_indicator_clear_of_the_action_bar(
    styled, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = listing.currentItem()
    palette = listing.viewport().palette()
    base = palette.color(QPalette.ColorRole.Base)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    option = _row_option(listing, item, _SELECTED_ACTIVE)
    padding = listing.header.style().pixelMetric(
        QStyle.PixelMetric.PM_HeaderMargin
    )

    image = _render_row(listing, item, _SELECTED_ACTIVE, base)
    indicator = _rail_columns(image, highlight)
    bar_left = listing.action_bar.geometry().left()

    assert indicator
    assert bar_left > max(indicator)
    assert bar_left >= _SELECTION_INDICATOR_GAP
    first_glyph = _first_glyph_x(image, _cell_pen(option), 0)
    assert first_glyph >= max(padding, tasklist._DATE_TEXT_LEFT_PADDING)


def test_the_indicator_of_a_selected_row_is_rounded_at_both_ends(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = listing.currentItem()
    palette = listing.viewport().palette()
    base = palette.color(QPalette.ColorRole.Base)
    highlight = palette.color(QPalette.ColorRole.Highlight)

    # the lines meet the rail at its two ends, so the rail is painted on its
    # own here: a whole row would hold the colour at both of its extremes
    option = _row_option(listing, item, _SELECTED_ACTIVE)
    image = QImage(option.rect.size(), QImage.Format.Format_RGB32)
    image.fill(base)
    painter = QPainter(image)
    tasklist._paint_selection(painter, option)
    painter.end()

    # the rail runs at full height between its ends, and a rounded corner
    # keeps its two extremes off the rail: the tint fills them instead
    assert image.pixelColor(0, image.height() // 2) == highlight
    assert image.pixelColor(0, 0) != highlight
    assert image.pixelColor(0, image.height() - 1) != highlight


def test_the_selected_area_is_tinted_from_the_task_row_to_the_bottom_of_the_band(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    item = listing.currentItem()
    palette = listing.viewport().palette()
    base = palette.color(QPalette.ColorRole.Base)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    tint = tasklist._blend(base, highlight, tasklist._SELECTION_TINT_WEIGHT)
    band_top = listing.delegate.min_height

    image = _render_row(listing, item, _SELECTED_ACTIVE, base)

    # both lines carry the selection: the rail at the left of each of them,
    # and the faint tint across the rest, under the action bar included
    assert image.height() > band_top
    for y in (band_top // 2, band_top + 2):
        rail = {image.pixelColor(x, y).rgb() for x in range(tasklist._SELECTION_INDICATOR_WIDTH)}
        assert rail == {highlight.rgb()}
    # the tint crosses the task row just past the rail, and fills the band,
    # where no cell is painted, from the rail to the right edge
    assert image.pixelColor(tasklist._SELECTION_INDICATOR_WIDTH, band_top // 2) == tint
    assert {image.pixelColor(x, band_top + 2).rgb() for x in range(tasklist._SELECTION_INDICATOR_WIDTH, image.width())} == {tint.rgb()}
    # the tint reads apart from the plain background and from the full rail
    assert tint != base
    assert tint != highlight
