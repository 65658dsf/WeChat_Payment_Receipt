# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Any, Iterable, List, Optional

from utools.ui.inspector import (
    _find_uia_top_windows,
    _safe_get,
    _safe_method,
    _uia_control_to_info,
)


def find_first_uia_top_window(
    desktop: Any,
    pid: Optional[int],
    window_title: str,
) -> Any:
    top_windows = _find_uia_top_windows(desktop.windows(), pid, window_title)
    if not top_windows:
        pid_text = f"PID为{pid}，" if pid is not None else ""
        raise RuntimeError(f"未找到{pid_text}标题包含“{window_title}”的窗口.")

    candidate = top_windows[0]
    if is_usable_top_window(candidate):
        return candidate

    candidate_info = _uia_control_to_info(candidate, 0, 0, "0")
    process_id = candidate_info.get("process_id")
    if isinstance(process_id, int):
        for window in _find_uia_top_windows(desktop.windows(), process_id, ""):
            if is_usable_top_window(window):
                return window

    return candidate


def is_usable_top_window(window: Any) -> bool:
    info = _uia_control_to_info(window, 0, 0, "0")
    rectangle = info.get("rectangle") or {}
    if info.get("visible") is False:
        return False
    if int(rectangle.get("width") or 0) <= 0 or int(rectangle.get("height") or 0) <= 0:
        return False
    if int(rectangle.get("left") or 0) < -10000 or int(rectangle.get("top") or 0) < -10000:
        return False
    return True


def iter_uia_tree(control: Any, max_depth: Optional[int] = None) -> Iterable[tuple[Any, int]]:
    stack: List[tuple[Any, int]] = [(control, 0)]
    while stack:
        current, depth = stack.pop()
        yield current, depth

        if max_depth is not None and depth >= max_depth:
            continue

        children = _safe_method(current, "children", []) or []
        for child in reversed(children):
            stack.append((child, depth + 1))


def uia_text_blob(control: Any) -> str:
    element = getattr(control, "element_info", control)
    parts = [
        _safe_get(lambda: element.name, ""),
        _safe_method(control, "window_text", ""),
        _safe_method(control, "get_value", ""),
    ]
    return " ".join(str(part) for part in parts if part)


def find_uia_click_target(
    root: Any,
    text: str,
    max_depth: Optional[int] = None,
) -> Optional[Any]:
    candidates: List[tuple[tuple[int, int, int], Any]] = []

    for control, depth in iter_uia_tree(root, max_depth):
        info = _uia_control_to_info(control, 0, depth, "candidate")
        blob = uia_text_blob(control)
        rectangle = info.get("rectangle") or {}
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        area = width * height
        control_type = info.get("control_type") or ""

        if text not in blob or width <= 0 or height <= 0:
            continue
        if info.get("visible") is False or info.get("enabled") is False:
            continue
        if control_type == "Document":
            continue

        priority = 0
        if control_type == "Button":
            priority -= 1000
        if info.get("name") == text or info.get("text") == text:
            priority -= 100
        if control_type in {"Text", "Hyperlink"}:
            priority -= 30

        candidates.append(((priority, area, -depth), control))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def click_relative(control: Any, x_ratio: float, y_ratio: float) -> tuple[int, int]:
    """按控件矩形相对坐标点击，并返回实际屏幕坐标."""

    from pywinauto import mouse  # type: ignore

    info = _uia_control_to_info(control, 0, 0, "click-root")
    rectangle = info.get("rectangle") or {}
    left = int(rectangle.get("left") or 0)
    top = int(rectangle.get("top") or 0)
    width = int(rectangle.get("width") or 0)
    height = int(rectangle.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("目标控件矩形无效，无法点击.")

    x = left + int(width * x_ratio)
    y = top + int(height * y_ratio)
    mouse.click(button="left", coords=(x, y))
    return x, y


def paste_text(text: str, clear_existing: bool = True) -> None:
    """使用 Windows 剪贴板向当前焦点控件粘贴文本."""

    from pywinauto import keyboard  # type: ignore

    set_clipboard_text(text)
    if clear_existing:
        keyboard.send_keys("^a")
        time.sleep(0.05)
    keyboard.send_keys("^v")
    time.sleep(0.1)


def set_clipboard_text(text: str) -> None:
    """设置 Windows Unicode 剪贴板文本."""

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    data = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())

    ctypes.memmove(locked, data, len(data))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise ctypes.WinError(ctypes.get_last_error())
        handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)


def wait_for_visible_uia_text(
    root: Any,
    text: str,
    timeout_seconds: float,
) -> Optional[Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if uia_tree_has_visible_text(root, text, max_depth=8):
            return root
        time.sleep(0.2)
    return None


def uia_tree_has_visible_text(control: Any, text: str, max_depth: Optional[int] = None) -> bool:
    for item, depth in iter_uia_tree(control, max_depth):
        info = _uia_control_to_info(item, 0, depth, "visible-text")
        rectangle = info.get("rectangle") or {}
        if info.get("control_type") == "Document":
            continue
        if info.get("visible") is False:
            continue
        if int(rectangle.get("width") or 0) <= 0 or int(rectangle.get("height") or 0) <= 0:
            continue
        if text in uia_text_blob(item):
            return True
    return False
