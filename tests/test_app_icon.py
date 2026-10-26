import ctypes
import importlib.util
import struct
import sys
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QImage

from mktsk.gui.app_icon import (
    APP_ID,
    DESKTOP_FILE_NAME,
    ICON_SIZES,
    _stroke_widths,
    app_icon,
    render_icon_image,
    set_app_identity,
)

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
