import ctypes
import sys
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mktsk.gui import windows_snap


@pytest.fixture(autouse=True)
def clear_user32_cache():
    windows_snap._user32.cache_clear()
    yield
    windows_snap._user32.cache_clear()


def _use_windows(monkeypatch):
    monkeypatch.setattr(windows_snap, "_is_windows", lambda: True)
    fake = MagicMock()
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=fake), raising=False)
    return fake


def _message(message_id, w_param, l_param=0, h_wnd=7):
    msg = wintypes.MSG()
    msg.message = message_id
    msg.wParam = w_param
    msg.lParam = l_param
    msg.hWnd = h_wnd
    return msg


def test_not_windows_calls_nothing(monkeypatch):
    monkeypatch.setattr(windows_snap, "_is_windows", lambda: False)
    fake = MagicMock()
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=fake), raising=False)
    windows_snap.enable_snap_styles(123)
    assert fake.mock_calls == []
    assert windows_snap.handle_native_event(b"windows_generic_MSG", 0) is None
    assert fake.mock_calls == []


def test_is_windows_true(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert windows_snap._is_windows() is True


def test_is_windows_false(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert windows_snap._is_windows() is False


def test_enable_snap_styles_adds_flags(monkeypatch):
    fake = _use_windows(monkeypatch)
    fake.GetWindowLongPtrW.return_value = 0x00000000
    windows_snap.enable_snap_styles(123)
    fake.GetWindowLongPtrW.assert_called_once_with(123, windows_snap.GWL_STYLE)
    expected = (
        0x00000000
        | windows_snap.WS_CAPTION
        | windows_snap.WS_THICKFRAME
        | windows_snap.WS_MINIMIZEBOX
        | windows_snap.WS_MAXIMIZEBOX
    )
    fake.SetWindowLongPtrW.assert_called_once_with(
        123, windows_snap.GWL_STYLE, expected
    )
    fake.SetWindowPos.assert_called_once_with(
        123, None, 0, 0, 0, 0, windows_snap.SWP_FLAGS
    )


def test_other_event_type_returns_none(monkeypatch):
    fake = _use_windows(monkeypatch)
    assert windows_snap.handle_native_event(b"other", 0) is None
    assert fake.mock_calls == []


def test_other_message_returns_none(monkeypatch):
    fake = _use_windows(monkeypatch)
    msg = _message(0x0001, 1)
    assert (
        windows_snap.handle_native_event(b"windows_generic_MSG", ctypes.addressof(msg))
        is None
    )
    fake.IsZoomed.assert_not_called()


def test_wparam_zero_returns_none(monkeypatch):
    fake = _use_windows(monkeypatch)
    msg = _message(windows_snap.WM_NCCALCSIZE, 0)
    assert (
        windows_snap.handle_native_event(b"windows_generic_MSG", ctypes.addressof(msg))
        is None
    )
    fake.IsZoomed.assert_not_called()


def test_not_zoomed_returns_true_and_unchanged_rect(monkeypatch):
    fake = _use_windows(monkeypatch)
    fake.IsZoomed.return_value = False
    msg = _message(windows_snap.WM_NCCALCSIZE, 1)
    params = windows_snap.NCCALCSIZE_PARAMS()
    rect = params.rgrc[0]
    rect.left, rect.top, rect.right, rect.bottom = 0, 0, 100, 100
    msg.lParam = ctypes.addressof(params)
    assert windows_snap.handle_native_event(
        b"windows_generic_MSG", ctypes.addressof(msg)
    ) == (True, 0)
    assert (rect.left, rect.top, rect.right, rect.bottom) == (0, 0, 100, 100)


def test_zoomed_shrinks_rect(monkeypatch):
    fake = _use_windows(monkeypatch)
    fake.IsZoomed.return_value = True
    fake.GetDpiForWindow.return_value = 144
    fake.GetSystemMetricsForDpi.side_effect = lambda index, dpi: {
        windows_snap.SM_CXSIZEFRAME: 8,
        windows_snap.SM_CYSIZEFRAME: 9,
        windows_snap.SM_CXPADDEDBORDER: 3,
    }[index]
    msg = _message(windows_snap.WM_NCCALCSIZE, 1)
    params = windows_snap.NCCALCSIZE_PARAMS()
    rect = params.rgrc[0]
    rect.left, rect.top, rect.right, rect.bottom = 0, 0, 100, 100
    msg.lParam = ctypes.addressof(params)
    assert windows_snap.handle_native_event(
        b"windows_generic_MSG", ctypes.addressof(msg)
    ) == (True, 0)
    assert (rect.left, rect.top, rect.right, rect.bottom) == (11, 12, 89, 88)
    fake.GetDpiForWindow.assert_called_once_with(7)
    fake.GetSystemMetricsForDpi.assert_any_call(windows_snap.SM_CXPADDEDBORDER, 144)
    fake.GetSystemMetricsForDpi.assert_any_call(windows_snap.SM_CXSIZEFRAME, 144)
    fake.GetSystemMetricsForDpi.assert_any_call(windows_snap.SM_CYSIZEFRAME, 144)


def test_user32_cached_and_declared(monkeypatch):
    fake = _use_windows(monkeypatch)
    first = windows_snap._user32()
    second = windows_snap._user32()
    assert first is second is fake
    assert fake.GetWindowLongPtrW.argtypes == [wintypes.HWND, ctypes.c_int]
    assert fake.GetWindowLongPtrW.restype == ctypes.c_ssize_t
    assert fake.SetWindowLongPtrW.argtypes == [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_ssize_t,
    ]
    assert fake.SetWindowLongPtrW.restype == ctypes.c_ssize_t
    assert fake.SetWindowPos.argtypes == [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    assert fake.SetWindowPos.restype == wintypes.BOOL
    assert fake.IsZoomed.argtypes == [wintypes.HWND]
    assert fake.IsZoomed.restype == wintypes.BOOL
    assert fake.GetDpiForWindow.argtypes == [wintypes.HWND]
    assert fake.GetDpiForWindow.restype == wintypes.UINT
    assert fake.GetSystemMetricsForDpi.argtypes == [ctypes.c_int, wintypes.UINT]
    assert fake.GetSystemMetricsForDpi.restype == ctypes.c_int
