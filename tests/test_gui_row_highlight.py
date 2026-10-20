"""The lines a selected row paints along its top and bottom edges."""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QStyle

from mktsk.gui import tasklist
from mktsk.gui.tasklist import _COUNT_ROLE
from tests.gui_helpers import find_task, render_row, select_task, task_listing

SHORT_TITLE = "Fix"

_SELECTED = (
    QStyle.StateFlag.State_Enabled
    | QStyle.StateFlag.State_Selected
    | QStyle.StateFlag.State_Active
)
_UNSELECTED = QStyle.StateFlag.State_Enabled


def _half_width(listing):
    """Half the total width of all the columns of a row, from the header."""
    header = listing.header
    total = sum(header.sectionSize(column) for column in range(header.count()))
    return total // 2


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


def test_the_lines_of_a_selected_row_carry_the_indicator_colour_and_thickness(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    thickness = tasklist._SELECTION_INDICATOR_WIDTH
    half = _half_width(listing)
    band_top = listing.delegate.min_height

    # the indicator keeps its colour at the middle of the left edge
    assert image.pixelColor(0, image.height() // 2) == highlight
    # the top line is painted in that colour, as thick as the indicator
    for y in range(thickness):
        assert image.pixelColor(half - 1, y) == highlight
    assert image.pixelColor(half - 1, thickness) == tint
    # and so is the bottom line, at the bottom edge of the task row
    for y in range(band_top - thickness, band_top):
        assert image.pixelColor(half - 1, y) == highlight
    assert image.pixelColor(half - 1, band_top - thickness - 1) == tint


def test_the_lines_of_a_selected_row_start_at_the_left_edge(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    half = _half_width(listing)
    band_top = listing.delegate.min_height

    # the rail rounds off at its top end, so only the line can ink that corner
    assert image.pixelColor(0, 0) == highlight
    # the bottom line runs the whole way from the left edge to the cut
    for x in range(half):
        assert image.pixelColor(x, band_top - 1) == highlight


def test_the_lines_of_a_selected_row_stop_at_half_the_row_width(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    half = _half_width(listing)
    band_top = listing.delegate.min_height

    assert half < image.width()
    # the pixel just before the half is painted, the one at the half is not
    assert image.pixelColor(half - 1, 0) == highlight
    assert image.pixelColor(half, 0) == tint
    assert image.pixelColor(half - 1, band_top - 1) == highlight
    assert image.pixelColor(half, band_top - 1) == tint


def test_the_lines_of_a_selected_row_run_without_a_gap_across_the_cells(
    window, tmp_path, make_task
):
    listing, image = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    header = listing.header
    half = _half_width(listing)
    band_top = listing.delegate.min_height
    borders = [
        header.sectionPosition(column) for column in range(1, header.count())
    ]

    # a cell border really sits inside the lines, before their cut
    assert any(0 < border < half for border in borders)
    for x in range(half):
        assert image.pixelColor(x, 0) == highlight
        assert image.pixelColor(x, band_top - 1) == highlight


def test_the_cut_of_the_lines_follows_a_resized_column(
    qtbot, window, tmp_path, make_task
):
    listing, _ = _selected_row(window, tmp_path, make_task)
    highlight = _highlight(listing)
    tint = _tint(listing)
    header = listing.header
    old_half = _half_width(listing)

    header.resizeSection(1, header.sectionSize(1) + 200)
    qtbot.wait(1)
    new_half = _half_width(listing)
    band_top = listing.delegate.min_height
    image = render_row(listing, listing.currentItem(), _SELECTED)

    # the cut moved with the column: the old cut is inside the lines now
    assert new_half == old_half + 100
    assert new_half < image.width()
    assert image.pixelColor(old_half, band_top - 1) == highlight
    assert image.pixelColor(new_half - 1, band_top - 1) == highlight
    assert image.pixelColor(new_half, band_top - 1) == tint


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

    # the rail still fills the left edge down the row, past the top line...
    for y in range(image.height() - thickness):
        assert image.pixelColor(0, y) == highlight
    # ...is exactly as wide as it was, with the tint right beside it...
    assert image.pixelColor(thickness - 1, image.height() // 2) == highlight
    assert image.pixelColor(thickness, image.height() // 2) == tint
    # ...and still rounds off at its bottom end
    assert image.pixelColor(0, image.height() - 1) != highlight
