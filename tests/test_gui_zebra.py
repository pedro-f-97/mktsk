"""Zebra stripes on task rows and the fill of a category separator."""

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionViewItem,
)

from mktsk.gui.tasklist import (
    _ENTRY_ROLE,
    _SEPARATOR_WEIGHT,
    _ZEBRA_WEIGHT,
    _blend,
    _colour_group,
    _contrast_ratio,
    _relative_luminance,
)
from tests.gui_helpers import (
    click_heading,
    render_row,
    row_background,
    task_listing,
)

_UNSELECTED = QStyle.StateFlag.State_Enabled
_SELECTED = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
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
    qapp.setStyle(_NoSelectionStyle(qapp.style()))
    yield
    style = QStyleFactory.create(name)
    if style is not None:
        qapp.setStyle(style)


def test_a_selected_row_keeps_the_base_and_a_striped_row_does_not(
    no_selection_style, window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    listing = task_listing(window, tmp_path.name)
    item = listing.item(1)
    base, text = _colours(listing, _UNSELECTED)
    stripe = _blend(base, text, _ZEBRA_WEIGHT)

    assert row_background(render_row(listing, item, _UNSELECTED)) == stripe
    assert row_background(render_row(listing, item, _SELECTED)) == base


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
