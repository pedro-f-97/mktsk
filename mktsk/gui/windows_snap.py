"""Aero Snap helpers for frameless windows on Windows.

Frameless windows lack WS_THICKFRAME and WS_MAXIMIZEBOX, which Windows needs
for Aero Snap; WM_NCCALCSIZE is answered so the native frame stays invisible.
This module is Windows-only and inert on other platforms.
"""

import ctypes
import sys
from ctypes import wintypes
from functools import cache

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020
WM_NCCALCSIZE = 0x0083
SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


def _is_windows() -> bool:
    return sys.platform == "win32"


@cache
def _user32():
    user32 = getattr(ctypes, "windll").user32  # noqa: B009
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
    user32.GetSystemMetricsForDpi.restype = ctypes.c_int
    return user32


def enable_snap_styles(hwnd: int) -> None:
    if not _is_windows():
        return
    user32 = _user32()
    old = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    style = old | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)


def handle_native_event(event_type: bytes, message: int) -> tuple[bool, int] | None:
    if not _is_windows():
        return None
    if bytes(event_type) != b"windows_generic_MSG":
        return None
    msg = wintypes.MSG.from_address(message)
    if not (msg.message == WM_NCCALCSIZE and msg.wParam):
        return None
    user32 = _user32()
    if user32.IsZoomed(msg.hWnd):
        params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
        dpi = user32.GetDpiForWindow(msg.hWnd)
        pad = user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
        fx = user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) + pad
        fy = user32.GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi) + pad
        rect = params.rgrc[0]
        rect.left += fx
        rect.top += fy
        rect.right -= fx
        rect.bottom -= fy
    return (True, 0)
