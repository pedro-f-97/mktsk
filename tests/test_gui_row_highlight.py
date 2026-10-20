"""The lines a selected row paints along its top and bottom edges."""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QStyle

from mktsk.gui import tasklist
from mktsk.gui.tasklist import _COUNT_ROLE
from tests.gui_helpers import find_task, render_row, select_task, task_listing

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
    return tasklist._blend(
        palette.color(QPalette.ColorRole.Base),
        palette.color(QPalette.ColorRole.Highlight),
        tasklist._SELECTION_TINT_WEIGHT,
    )


def _arm(listing):
    """The whole width a line paints: the rail's thickness plus its reach."""
    return tasklist._SELECTION_INDICATOR_WIDTH + tasklist._ROW_LINE_REACH


def _assert_bracket(listing, image):
    """Asserts the lines bracket the row at the rail's two extremes.

    The top line starts at the rail's first pixel row and the bottom one ends
    at its last, both run from the left edge to the end of the arm and no
    further, in the colour and the thickness of the rail.
    """
    highlight = _highlight(listing)
    tint = _tint(listing)
    thickness = tasklist._SELECTION_INDICATOR_WIDTH
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
    thickness = tasklist._SELECTION_INDICATOR_WIDTH
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
    thickness = tasklist._SELECTION_INDICATOR_WIDTH

    # the rail fills the left edge down the whole row, the lines inking the
    # corners its rounding leaves open...
    for y in range(image.height()):
        assert image.pixelColor(0, y) == highlight
    # ...is exactly as wide as it was, with the tint right beside it
    assert image.pixelColor(thickness - 1, image.height() // 2) == highlight
    assert image.pixelColor(thickness, image.height() // 2) == tint
