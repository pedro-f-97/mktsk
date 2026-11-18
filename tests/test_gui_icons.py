import ctypes
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from mktsk.gui import MainWindow
from mktsk.gui.app_icon import (
    APP_ID,
    DESKTOP_FILE_NAME,
    ICON_SIZES,
    _stroke_widths,
    app_icon,
    render_icon_image,
    set_app_identity,
)
from mktsk.gui.icons import (
    _ICON_SIZE,
    _draw_choose,
    _draw_close,
    _draw_folder,
    _draw_plus,
    _draw_refresh,
    _draw_reopen,
    _draw_state,
    _draw_up,
    _icon_button,
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


def test_the_up_icon_points_up(qapp):
    ink = _ink(_draw_up)

    # a shaft down the middle, and a head that is wider than it at the base
    assert ink[5][9] is True
    assert ink[14][9] is True
    assert sum(ink[5]) < sum(ink[9])


def test_the_choose_icon_is_more_than_the_folder(qapp):
    # choosing a directory is a folder, with the arrow that tells it apart
    assert _ink(_draw_choose) != _ink(_draw_folder)
    assert _ink(_draw_choose) != _ink(_draw_up)


def test_the_refresh_icon_is_not_the_reopen_icon(qapp):
    # reloading the listing turns one way, restoring a task the other
    assert _ink(_draw_refresh) != _ink(_draw_reopen)


def _leading_ink(icon):
    """The first painted pixel of an icon, which is its stroke colour."""
    image = icon.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                return color
    raise AssertionError("the icon has no ink")


def test_the_button_icon_follows_the_palette(qapp):
    light = QWidget()
    dark = QWidget()
    palette = dark.palette()
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    dark.setPalette(palette)

    light_button = _icon_button(light, "Up", _draw_up, "Up")
    dark_button = _icon_button(dark, "Up", _draw_up, "Up")

    assert _leading_ink(light_button.icon()) != _leading_ink(dark_button.icon())


def test_the_disabled_icon_differs_from_the_enabled_one(qapp):
    parent = QWidget()
    button = _icon_button(parent, "Up", _draw_up, "Up")
    size = QSize(_ICON_SIZE, _ICON_SIZE)

    enabled = button.icon().pixmap(size, QIcon.Mode.Normal).toImage()
    disabled = button.icon().pixmap(size, QIcon.Mode.Disabled).toImage()

    assert enabled != disabled


def test_the_navigation_buttons_are_icons_with_a_name(window):
    expected = {
        window.choose_button: "Choose...",
        window.up_button: "Up",
        window.refresh_button: "Refresh",
    }

    for button, text in expected.items():
        assert button.text() == ""
        assert button.icon().isNull() is False
        assert button.toolTip() == text
        assert button.accessibleName() == text


_BLACK = QColor("black").rgba()
_WHITE = QColor("white").rgba()


def _load_make_icon():
    """Loads the generator script, which lives outside the package."""
    path = Path(__file__).resolve().parents[1] / "tools" / "make_icon.py"
    spec = importlib.util.spec_from_file_location("make_icon", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MAKE_ICON = _load_make_icon()


def _ico_entries(data):
    """Returns the header and the entries of an icon file.

    Each entry is returned as its width, height, planes, bits per pixel, the
    size of its payload and the offset the payload starts at.
    """
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    entries = []

    for index in range(count):
        start = 6 + index * 16
        width, height, _, _, planes, bits, size, offset = struct.unpack(
            "<BBBBHHII", data[start : start + 16]
        )
        entries.append((width, height, planes, bits, size, offset))

    return reserved, kind, entries


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


def test_the_icon_file_starts_with_the_header_of_an_icon():
    data = _MAKE_ICON.build_ico([render_icon_image(16)])

    reserved, kind, count = struct.unpack("<HHH", data[:6])

    assert (reserved, kind, count) == (0, 1, 1)


def test_every_image_has_an_entry():
    images = [render_icon_image(size) for size in (16, 32, 48)]

    data = _MAKE_ICON.build_ico(images)
    _, _, count = struct.unpack("<HHH", data[:6])

    assert count == len(images)


def test_the_largest_image_is_stored_as_zero():
    data = _MAKE_ICON.build_ico([render_icon_image(256)])

    width, height = struct.unpack("<BB", data[6:8])

    assert (width, height) == (0, 0)


def test_every_payload_is_a_png():
    images = [render_icon_image(size) for size in (16, 48, 256)]

    data = _MAKE_ICON.build_ico(images)
    _, _, entries = _ico_entries(data)

    for _, _, _, _, _, offset in entries:
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"


def test_the_entries_point_at_the_payloads():
    images = [render_icon_image(size) for size in (16, 48, 256)]

    data = _MAKE_ICON.build_ico(images)
    _, _, entries = _ico_entries(data)

    for index, (_, _, planes, bits, size, offset) in enumerate(entries):
        assert (planes, bits) == (1, 32)
        assert offset + size <= len(data)
        if index + 1 < len(entries):
            assert entries[index + 1][5] == offset + size

    assert entries[-1][5] + entries[-1][4] == len(data)


def test_the_generator_writes_the_assets(tmp_path):
    _MAKE_ICON.main(out_dir=tmp_path)

    icon = (tmp_path / "app.ico").read_bytes()
    picture = (tmp_path / "app.png").read_bytes()

    assert icon[:4] == b"\x00\x00\x01\x00"
    assert picture[:8] == b"\x89PNG\r\n\x1a\n"

    image = QImage(str(tmp_path / "app.png"))
    assert image.width() == 256
    assert image.height() == 256


class _RecordingShell32:
    """Stands for the shell32 api, and records the app id it is given."""

    def __init__(self, calls):
        self._calls = calls

    def SetCurrentProcessExplicitAppUserModelID(self, app_id):
        self._calls.append(app_id)


class _FailingShell32:
    """Stands for the shell32 api when the call fails."""

    def SetCurrentProcessExplicitAppUserModelID(self, app_id):
        raise OSError("no shell here")


class _EmptyShell32:
    """Stands for a shell32 that does not carry the api."""


def _windll(shell32: Any) -> Any:
    """Builds a fake ctypes.windll around the given shell32."""

    class _Windll:
        shell32: Any

    windll = _Windll()
    windll.shell32 = shell32
    return windll


def _recording_gui_application(calls):
    """Builds a fake QGuiApplication that records the desktop file name."""

    class _GuiApplication:
        @staticmethod
        def setDesktopFileName(name):
            calls.append(name)

    return _GuiApplication


def test_the_app_id_is_set_on_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        ctypes, "windll", _windll(_RecordingShell32(calls)), raising=False
    )

    set_app_identity()

    assert calls == [APP_ID]


def test_a_failing_call_is_ignored(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(ctypes, "windll", _windll(_FailingShell32()), raising=False)

    # the failure is swallowed, so the call comes back without raising
    set_app_identity()


def test_a_missing_shell_api_is_ignored(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(ctypes, "windll", _windll(_EmptyShell32()), raising=False)

    # the missing api is swallowed, so the call comes back without raising
    set_app_identity()


def test_the_frozen_executable_keeps_the_identity_of_its_exe(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        ctypes, "windll", _windll(_RecordingShell32(calls)), raising=False
    )

    set_app_identity()

    assert calls == []


def test_the_desktop_file_name_is_set_on_linux(qapp, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    previous = QGuiApplication.desktopFileName()
    try:
        set_app_identity()

        assert QGuiApplication.desktopFileName() == DESKTOP_FILE_NAME
    finally:
        QGuiApplication.setDesktopFileName(previous)


def test_other_platforms_are_left_alone(monkeypatch):
    calls = []
    desktops = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        ctypes, "windll", _windll(_RecordingShell32(calls)), raising=False
    )
    monkeypatch.setattr(
        "mktsk.gui.app_icon.QGuiApplication", _recording_gui_application(desktops)
    )

    set_app_identity()

    assert calls == []
    assert desktops == []


# The drawn icons and the hint must follow the application palette.
#
# When the system theme switches from light to dark without closing the program,
# every component that draws its own colour has to re-derive it from the current
# palette. The rest of the interface already does this: it reads palette roles at
# paint time, so a re-polish of the window is enough. The drawn icons and the
# ``New tasks in ...`` hint froze their colour at build time, so they stay in the
# light colour and become almost imperceptible in dark mode.


_THEME_ICON_SIZE = 18


def _theme(text: str, button_text: str) -> QPalette:
    """Builds a palette; light when the text is dark, dark when it is white."""
    dark = text == "#ffffff"
    palette = QPalette()
    palette.setColor(
        QPalette.ColorRole.Window, QColor("#2b2b2b" if dark else QColor("#ffffff"))
    )
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(button_text))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(
        QPalette.ColorRole.Base, QColor("#3b3b3b" if dark else QColor("#ffffff"))
    )
    return palette


def _theme_ink(icon) -> QColor:
    """The dominant colour of an icon's essentially opaque painted pixels.

    Antialiased edge pixels carry partial alpha and are ignored, so the result
    is the solid stroke colour the icon is drawn with.
    """
    image = icon.pixmap(QSize(_THEME_ICON_SIZE, _THEME_ICON_SIZE)).toImage()
    counts = Counter()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 200:
                counts[color.rgb()] += 1
    return QColor.fromRgb(counts.most_common(1)[0][0])


def _switch_theme(window: MainWindow, palette: QPalette) -> None:
    """Simulates the system theme changing while the window stays open.

    This is what makes widgets re-resolve their colours from the new
    application palette, the same way a real theme change re-polishes the
    window. Widgets that kept an explicit colour keep it; the rest follow.
    """
    QApplication.setPalette(palette)
    style = window.style()
    style.unpolish(window)
    style.polish(window)
    QApplication.processEvents()


def test_the_hint_follows_the_palette(window, qapp):
    _switch_theme(window, _theme("#000000", "#000000"))
    before = window.target_label.palette().color(QPalette.ColorRole.WindowText)
    assert before == QColor("#000000")

    _switch_theme(window, _theme("#ffffff", "#ffffff"))

    after = window.target_label.palette().color(QPalette.ColorRole.WindowText)
    assert after == QColor("#ffffff")


def test_the_drawn_icon_follows_the_palette(window, qapp):
    _switch_theme(window, _theme("#000000", "#000000"))
    before = _theme_ink(window.refresh_button.icon())
    assert before == QColor("#000000")

    _switch_theme(window, _theme("#ffffff", "#ffffff"))

    after = _theme_ink(window.refresh_button.icon())
    dark = QColor("#ffffff")
    assert after != before
    assert after == dark
