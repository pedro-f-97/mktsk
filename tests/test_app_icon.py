import pytest
from PySide6.QtGui import QColor, QImage

from mktsk.gui.app_icon import (
    ICON_SIZES,
    _stroke_widths,
    app_icon,
    render_icon_image,
)

_BLACK = QColor("black").rgba()
_WHITE = QColor("white").rgba()


def _pixels(image):
    return {
        image.pixelColor(x, y).rgba()
        for x in range(image.width())
        for y in range(image.height())
    }


def _covered_bounds(image):
    """Returns the box of the pixels the drawing covers.

    The alpha of an ARGB32 image sits in the last byte of each pixel, so the
    box is read from the raw bytes of the image.
    """
    data = image.bits()
    width = image.width()
    left, top = width, width
    right, bottom = -1, -1

    for index in range(width * image.height()):
        if data[index * 4 + 3] == 0:
            continue
        x = index % width
        y = index // width
        left = min(left, x)
        top = min(top, y)
        right = max(right, x)
        bottom = max(bottom, y)

    return left, top, right, bottom


def test_small_sizes_get_thicker_strokes():
    assert _stroke_widths(16)[0] > _stroke_widths(256)[0]
    assert _stroke_widths(16)[1] > _stroke_widths(256)[1]


@pytest.mark.parametrize(
    ("size", "widths"),
    (
        (16, (16.0, 9.0)),
        (24, (16.0, 9.0)),
        (32, (12.0, 6.5)),
        (48, (9.0, 5.0)),
        (64, (9.0, 5.0)),
        (128, (7.0, 3.5)),
        (256, (7.0, 3.5)),
    ),
)
def test_each_size_carries_its_own_strokes(size, widths):
    assert _stroke_widths(size) == widths


@pytest.mark.parametrize("size", (128, 256))
def test_large_sizes_keep_the_base_strokes(size):
    assert _stroke_widths(size) == (7.0, 3.5)


@pytest.mark.parametrize("size", ICON_SIZES)
def test_render_icon_image_is_square_and_of_the_requested_size(size):
    image = render_icon_image(size)

    assert image.width() == size
    assert image.height() == size


@pytest.mark.parametrize("size", (16, 32, 256))
def test_the_corner_of_the_icon_is_transparent(size):
    image = render_icon_image(size)

    assert image.pixelColor(0, 0).alpha() == 0


@pytest.mark.parametrize("size", ICON_SIZES)
def test_the_icon_has_an_opaque_black_stroke(size):
    colors = _pixels(render_icon_image(size))

    assert _BLACK in colors


@pytest.mark.parametrize("size", (48, 64, 128, 256))
def test_the_larger_icons_keep_the_white_outline(size):
    colors = _pixels(render_icon_image(size))

    assert _WHITE in colors


@pytest.mark.parametrize("size", (16, 24, 32))
def test_the_smaller_icons_keep_a_visible_outline(size):
    image = render_icon_image(size)

    assert any(
        image.pixelColor(x, y).alpha() > 0 and image.pixelColor(x, y).red() > 127
        for x in range(size)
        for y in range(size)
    )


@pytest.mark.parametrize("size", (64, 256))
def test_the_drawing_sits_in_the_middle_of_the_icon(size):
    image = render_icon_image(size)
    left, top, right, bottom = _covered_bounds(image)

    assert abs((left + right) / 2 - size / 2) <= size * 0.02
    assert abs((top + bottom) / 2 - size / 2) <= size * 0.02


def test_the_drawing_keeps_clear_of_the_edges():
    image = render_icon_image(256)
    left, top, right, bottom = _covered_bounds(image)

    assert left > 0
    assert top > 0
    assert right < image.width() - 1
    assert bottom < image.height() - 1


@pytest.mark.parametrize("size", ICON_SIZES)
def test_rendering_the_same_size_twice_gives_the_same_image(size):
    assert render_icon_image(size) == render_icon_image(size)


def test_app_icon_reports_every_size(qapp):
    icon = app_icon()

    assert not icon.isNull()
    assert {size.width() for size in icon.availableSizes()} == set(ICON_SIZES)


def test_the_main_window_carries_the_icon(window):
    assert not window.windowIcon().isNull()


def test_the_icon_image_is_an_argb_image_of_the_base_grid():
    image = render_icon_image(32)

    assert image.format() == QImage.Format.Format_ARGB32
