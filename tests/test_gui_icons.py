from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from mktsk.gui.icons import (
    _ICON_SIZE,
    _draw_close,
    _draw_folder,
    _draw_plus,
    _draw_reopen,
    _draw_state,
    _stroked_icon,
)


def _ink(draw):
    """Renders an icon and returns its ink, one cell per logical pixel."""
    icon = _stroked_icon(QColor("#000000"), draw)
    image = icon.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()
    step = image.width() / image.deviceIndependentSize().width()
    return [
        [
            image.pixelColor(round(x * step), round(y * step)).alpha() > 0
            for x in range(_ICON_SIZE)
        ]
        for y in range(_ICON_SIZE)
    ]


def _painted(ink, along, at):
    """Whether a line of the icon has ink, across a row or a column."""
    if along == "column":
        return any(ink[y][at] for y in range(_ICON_SIZE))
    return any(ink[at])


def test_the_folder_outline_is_closed(qapp):
    ink = _ink(_draw_folder)

    # every side of a closed folder is drawn, the left one like the right one
    assert _painted(ink, "column", 1) is True
    assert _painted(ink, "column", 16) is True
    assert _painted(ink, "row", 15) is True

    # and it is an outline, not a filled block
    assert ink[11][8] is False


def test_the_folder_has_a_tab_and_not_just_a_box(qapp):
    ink = _ink(_draw_folder)

    # the tab stands above the body, so the top is inked on the left only
    assert ink[4][5] is True
    assert ink[4][12] is False
    assert ink[6][12] is True


def test_the_plus_is_symmetric_about_its_centre(qapp):
    ink = _ink(_draw_plus)
    last = _ICON_SIZE - 1
    centre = _ICON_SIZE // 2

    # the bars cross at the middle of the icon, and reach as far either side
    assert ink[centre][centre] is True
    for offset in range(_ICON_SIZE):
        assert ink[centre][offset] == ink[centre][last - offset]
        assert ink[offset][centre] == ink[last - offset][centre]


def test_the_state_icon_is_a_ring_with_a_dot(qapp):
    ink = _ink(_draw_state)
    last = _ICON_SIZE - 1
    centre = _ICON_SIZE // 2

    # the ring and the dot inside it both sit on the middle of the icon
    assert ink[centre][centre] is True
    assert ink[centre][3] is True
    assert ink[centre][5] is False

    # and the ring is a ring: the same on both sides of the middle
    for offset in range(_ICON_SIZE):
        assert ink[centre][offset] == ink[centre][last - offset]


def test_the_close_icon_is_a_box_with_a_lid(qapp):
    ink = _ink(_draw_close)

    # the lid is a band across the top, with a slot in the middle of it
    assert _painted(ink, "row", 3) is True
    assert ink[5][9] is True

    # and the box under the lid is an outline rather than a filled block
    assert ink[12][9] is False
    assert ink[15][4] is True


def test_the_reopen_icon_is_not_the_resume_icon(qapp):
    # reopening an archived task is not adding a note, so the two icons must
    # draw different images
    assert _ink(_draw_reopen) != _ink(_draw_plus)
