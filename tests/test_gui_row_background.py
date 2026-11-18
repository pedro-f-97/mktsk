"""The lines a selected row paints along its top and bottom edges."""

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionViewItem,
)

from mktsk.gui import selection
from mktsk.gui.selection import (
    _SELECTION_TINT_WEIGHT,
    _blend,
    _colour_group,
    _contrast_ratio,
    _relative_luminance,
)
from mktsk.gui.taskrow import _COUNT_ROLE, _ENTRY_ROLE, _SEPARATOR_WEIGHT, _ZEBRA_WEIGHT
from tests.gui_helpers import (
    click_heading,
    find_task,
    render_row,
    row_background,
    select_task,
    task_listing,
)

SHORT_TITLE = "Fix"
OTHER_TITLE = "Check"

_SELECTED = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
_UNSELECTED = QStyle.StateFlag.State_Enabled


def _selected_row(window, tmp_path, make_task):
    """The listing of one task with its row selected, and that row rendered."""
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    image = render_row(listing, listing.currentItem(), _SELECTED)
    return listing, image


def _highlight(listing):
    """The colour the indicator rail and the lines are painted in."""
    return listing.viewport().palette().color(QPalette.ColorRole.Highlight)


def _tint(listing):
    """The faint colour a selected row is filled with."""
    palette = listing.viewport().palette()
    return selection._blend(
        palette.color(QPalette.ColorRole.Base),
        palette.color(QPalette.ColorRole.Highlight),
        selection._SELECTION_TINT_WEIGHT,
    )


def _arm(listing):
    """The whole width a line paints: the rail's thickness plus its reach."""
    return selection._SELECTION_INDICATOR_WIDTH + selection._ROW_LINE_REACH


def _assert_bracket(listing, image):
    """Asserts the lines bracket the row at the rail's two extremes.

    The top line starts at the rail's first pixel row and the bottom one ends
    at its last, both run from the left edge to the end of the arm and no
    further, in the colour and the thickness of the rail.
    """
    highlight = _highlight(listing)
    tint = _tint(listing)
    thickness = selection._SELECTION_INDICATOR_WIDTH
    reach = _arm(listing)
    rows = range(thickness)
    bottom = range(image.height() - thickness, image.height())

    for x in range(reach):
        assert all(image.pixelColor(x, y) == highlight for y in rows)
        assert all(image.pixelColor(x, y) == highlight for y in bottom)
    assert image.pixelColor(reach, 0) == tint
    assert image.pixelColor(reach, image.height() - 1) == tint
    assert not any(
        image.pixelColor(x, y) == highlight
        for y in range(image.height())
        for x in range(reach, image.width())
    )


def test_the_lines_of_a_selected_row_carry_the_indicator_colour_and_thickness(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    thickness = selection._SELECTION_INDICATOR_WIDTH
    probe = _arm(listing) - 1

    # the indicator keeps its colour at the middle of the left edge
    assert image.pixelColor(0, image.height() // 2) == highlight
    # the top line starts at the rail's first pixel row, as thick as the rail
    for y in range(thickness):
        assert image.pixelColor(probe, y) == highlight
    assert image.pixelColor(probe, thickness) == tint
    # and the bottom line ends at the rail's last pixel row
    for y in range(image.height() - thickness, image.height()):
        assert image.pixelColor(probe, y) == highlight
    assert image.pixelColor(probe, image.height() - thickness - 1) == tint


def test_the_lines_of_a_selected_row_bracket_it_at_the_rails_extremes(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)

    _assert_bracket(listing, image)


def test_the_arm_of_the_lines_is_the_rail_thickness_plus_the_reach(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    reach = _arm(listing)

    assert reach < image.width()
    # the last pixel of the arm is inked on both lines...
    assert image.pixelColor(reach - 1, 0) == highlight
    assert image.pixelColor(reach - 1, image.height() - 1) == highlight
    # ...and the pixel past it is not
    assert image.pixelColor(reach, 0) == tint
    assert image.pixelColor(reach, image.height() - 1) == tint


def test_the_lines_bracket_a_row_with_and_without_the_action_bar_line(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    other = make_task(tmp_path, "260919", OTHER_TITLE)
    window.navigate_to(tmp_path)
    listing = select_task(window, file)
    with_band = render_row(listing, listing.currentItem(), _SELECTED)
    without_band = render_row(listing, find_task(window, other), _SELECTED)

    # one row carries the band the action bar opens, the other has no line
    # for it, and the two bracket the same way at the rail's two ends
    assert (
        with_band.height() - without_band.height()
        == listing.delegate.accordion_height
    )
    _assert_bracket(listing, with_band)
    _assert_bracket(listing, without_band)


def test_an_unselected_row_carries_no_lines(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    highlight = _highlight(listing)
    image = render_row(listing, find_task(window, file), _UNSELECTED)

    assert not any(
        image.pixelColor(x, y) == highlight
        for y in range(image.height())
        for x in range(image.width())
    )


def test_a_category_separator_row_carries_no_lines(window, tmp_path, make_task):
    make_task(tmp_path, "260918", SHORT_TITLE)
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    highlight = _highlight(listing)
    tint = _tint(listing)
    heading = listing.item(0)

    # the heading takes the separator path, which paints no selection of its
    # own: no line, no rail and no tint reaches it
    assert heading.data(_COUNT_ROLE) is None
    image = render_row(listing, heading, _UNSELECTED)
    assert not any(
        image.pixelColor(x, y) in (highlight, tint)
        for y in range(image.height())
        for x in range(image.width())
    )


def test_the_indicator_of_a_selected_row_keeps_its_colour_and_its_width(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    thickness = selection._SELECTION_INDICATOR_WIDTH

    # the rail fills the left edge down the whole row, the lines inking the
    # corners its rounding leaves open...
    for y in range(image.height()):
        assert image.pixelColor(0, y) == highlight
    # ...is exactly as wide as it was, with the tint right beside it
    assert image.pixelColor(thickness - 1, image.height() // 2) == highlight
    assert image.pixelColor(thickness, image.height() // 2) == tint


# Zebra stripes on task rows and the fill of a category separator.


_MINIMUM_CONTRAST = 4.5
_SUBTLE = 1.15


def _colours(view, state):
    """The base and the text colour of the palette group a state implies."""
    group = _colour_group(state)
    palette = view.viewport().palette()
    return (
        palette.color(group, QPalette.ColorRole.Base),
        palette.color(group, QPalette.ColorRole.Text),
    )


def _striped(view, item):
    """Whether a rendered task row is drawn on the stripe colour."""
    base, text = _colours(view, _UNSELECTED)
    image = render_row(view, item, _UNSELECTED)
    background = row_background(image)
    assert background in (base, _blend(base, text, _ZEBRA_WEIGHT))
    return background == _blend(base, text, _ZEBRA_WEIGHT)


def _task_items(listing):
    return [
        listing.item(index)
        for index in range(listing.count())
        if listing.item(index).data(_ENTRY_ROLE) is not None
    ]


def _glyph(image, background):
    """The pixel of a row that stands furthest from its background."""
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


def test_blend_returns_the_endpoints_and_the_midpoint():
    base = QColor(10, 20, 30)
    text = QColor(110, 220, 230)

    assert _blend(base, text, 0.0) == base
    assert _blend(base, text, 1.0) == text
    assert _blend(base, text, 0.5) == QColor(60, 120, 130)


def test_blend_never_leaves_the_colour_range():
    base = QColor(0, 0, 0)
    text = QColor(255, 255, 255)

    for weight in (-0.5, 0.0, 0.03, 0.5, 0.97, 1.0, 1.5):
        blended = _blend(base, text, weight)
        for channel in (blended.red(), blended.green(), blended.blue()):
            assert 0 <= channel <= 255


def test_a_light_stripe_is_subtle_and_the_separator_is_darker():
    base = QColor("#ffffff")
    text = QColor("#000000")
    stripe = _blend(base, text, _ZEBRA_WEIGHT)
    separator = _blend(base, text, _SEPARATOR_WEIGHT)

    assert stripe != base
    assert _contrast_ratio(stripe, base) < _SUBTLE
    assert _relative_luminance(separator) < _relative_luminance(stripe)
    assert _contrast_ratio(text, separator) >= _MINIMUM_CONTRAST


def test_a_dark_stripe_is_lighter_and_keeps_the_text_readable():
    base = QColor("#1e1e1e")
    text = QColor("#e0e0e0")
    stripe = _blend(base, text, _ZEBRA_WEIGHT)
    separator = _blend(base, text, _SEPARATOR_WEIGHT)

    assert _relative_luminance(stripe) > _relative_luminance(base)
    assert _contrast_ratio(text, stripe) >= _MINIMUM_CONTRAST
    assert _contrast_ratio(text, separator) >= _MINIMUM_CONTRAST


def test_the_stripe_is_derived_from_the_palette(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window, tmp_path.name)
    palette = QPalette(listing.viewport().palette())
    palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    item = listing.item(1)

    image = render_row(listing, item, _UNSELECTED, palette)
    group = _colour_group(_UNSELECTED)
    base = palette.color(group, QPalette.ColorRole.Base)
    text = palette.color(group, QPalette.ColorRole.Text)
    stripe = _blend(base, text, _ZEBRA_WEIGHT)

    assert row_background(image) == stripe
    assert _relative_luminance(stripe) > _relative_luminance(base)
    assert _contrast_ratio(text, stripe) >= _MINIMUM_CONTRAST


def test_stripes_alternate_restart_and_survive_sort_and_refresh(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    make_task(tmp_path / "Veritas", "260920", "Baz")
    make_task(tmp_path / "Veritas", "260921", "Qux")
    window.navigate_to(tmp_path)
    listing = task_listing(window)

    expected = [False, True, False, True]
    assert [_striped(listing, item) for item in _task_items(listing)] == expected

    click_heading(window, 1)
    assert [_striped(listing, item) for item in _task_items(listing)] == expected

    window.refresh()
    assert [_striped(listing, item) for item in _task_items(listing)] == expected


class _NoSelectionStyle(QProxyStyle):
    """A style that paints no selection of its own."""

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
    name = qapp.style().objectName()
    qapp.setStyle(_NoSelectionStyle(QStyleFactory.create(name)))
    yield
    style = QStyleFactory.create(name)
    if style is not None:
        qapp.setStyle(style)


def test_a_selected_row_is_tinted_and_a_striped_row_does_not_become_one(
    no_selection_style, window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window, tmp_path.name)
    item = listing.item(1)
    base, text = _colours(listing, _UNSELECTED)
    stripe = _blend(base, text, _ZEBRA_WEIGHT)
    group = _colour_group(_SELECTED)
    palette = listing.viewport().palette()
    tint = _blend(
        palette.color(group, QPalette.ColorRole.Base),
        palette.color(group, QPalette.ColorRole.Highlight),
        _SELECTION_TINT_WEIGHT,
    )

    assert row_background(render_row(listing, item, _UNSELECTED)) == stripe
    # a selected row carries the selection of the delegate rather than a
    # stripe, and the style paints no selection of its own to cover that
    assert row_background(render_row(listing, item, _SELECTED)) == tint
    assert tint != base


def test_the_separator_keeps_the_task_text_and_fills_the_whole_row(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    heading = listing.item(0)
    task = listing.item(1)
    base, text = _colours(listing, _UNSELECTED)
    separator = _blend(base, text, _SEPARATOR_WEIGHT)

    image = render_row(listing, heading, QStyle.StateFlag.State_None)
    middle = image.height() // 2
    assert image.pixelColor(0, middle) == separator
    assert image.pixelColor(image.width() - 1, middle) == separator

    task_image = render_row(listing, task, _UNSELECTED)
    assert _glyph(image, separator) == _glyph(task_image, row_background(task_image))

    option = QStyleOptionViewItem()
    listing.delegate.initStyleOption(option, listing.indexFromItem(heading))
    assert option.font.bold()


def test_the_separator_text_is_the_task_text_not_the_disabled_grey(
    window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    recorder = _RecordingStyle(QStyleFactory.create(listing.style().objectName()))
    listing.setStyle(recorder)
    palette = QPalette(listing.viewport().palette())
    # the view hands a non-selectable separator a palette in the Disabled group,
    # which is where the style would otherwise read the grey text from
    palette.setCurrentColorGroup(QPalette.ColorGroup.Disabled)

    render_row(listing, listing.item(0), QStyle.StateFlag.State_None, palette)

    assert recorder.groups
    assert QPalette.ColorGroup.Disabled not in recorder.groups


class _RecordingStyle(QProxyStyle):
    """A style that records the palette group of every item it draws."""

    def __init__(self, base):
        super().__init__(base)
        self.groups = []

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem:
            self.groups.append(option.palette.currentColorGroup())
        super().drawControl(element, option, painter, widget)
