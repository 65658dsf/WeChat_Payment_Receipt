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


def enable_fast_timings() -> None:
    """降低 pywinauto 默认动作等待时间."""

    try:
        from pywinauto.timings import Timings  # type: ignore

        Timings.fast()
        Timings.after_clickinput_wait = 0.01
        Timings.after_setfocus_wait = 0.01
        Timings.after_sendkeys_key_wait = 0.001
    except Exception:
        return


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


def uia_control_search_info(control: Any) -> dict[str, Any]:
    """返回用于 UIA 搜索的轻量信息，避免遍历时重复读取子节点和值."""

    element = getattr(control, "element_info", control)
    rectangle = _safe_get(lambda: element.rectangle)
    name = _safe_get(lambda: element.name, "")
    text = "" if name else _safe_method(control, "window_text", "")
    value = "" if name or text else _safe_method(control, "get_value", "")
    visible = _safe_get(lambda: element.visible)
    if visible is None:
        visible = _safe_method(control, "is_visible")
    enabled = _safe_get(lambda: element.enabled)
    if enabled is None:
        enabled = _safe_method(control, "is_enabled")

    left = int(_safe_get(lambda: rectangle.left, 0) or 0)
    top = int(_safe_get(lambda: rectangle.top, 0) or 0)
    right = int(_safe_get(lambda: rectangle.right, 0) or 0)
    bottom = int(_safe_get(lambda: rectangle.bottom, 0) or 0)
    return {
        "name": name,
        "text": text,
        "value": value,
        "text_blob": " ".join(str(part) for part in (name, text, value) if part),
        "control_type": _safe_get(lambda: element.control_type, ""),
        "visible": visible,
        "enabled": enabled,
        "rectangle": {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": max(0, right - left),
            "height": max(0, bottom - top),
        },
    }


def find_uia_click_target(
    root: Any,
    text: str,
    max_depth: Optional[int] = None,
) -> Optional[Any]:
    candidates: List[tuple[tuple[int, int, int], Any]] = []

    for control, depth in iter_uia_tree(root, max_depth):
        info = uia_control_search_info(control)
        blob = info["text_blob"]
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
    try:
        mouse.click(button="left", coords=(x, y))
    except RuntimeError as exc:
        _raise_active_desktop_error(exc)
    return x, y


def click_screen_point(x: int, y: int) -> tuple[int, int]:
    """点击指定屏幕坐标，并返回实际点击点."""

    from pywinauto import mouse  # type: ignore

    try:
        mouse.click(button="left", coords=(x, y))
    except RuntimeError as exc:
        _raise_active_desktop_error(exc)
    return x, y


def invoke_or_click(control: Any) -> str:
    """优先用 UIA InvokePattern 点击控件，失败时才回退到鼠标点击."""

    invoke_error: Exception | None = None
    try:
        invoke = getattr(control, "invoke", None)
        if callable(invoke):
            invoke()
            return "invoke"
    except Exception as exc:
        invoke_error = exc

    try:
        iface_invoke = getattr(control, "iface_invoke", None)
        if iface_invoke is not None:
            iface_invoke.Invoke()
            return "iface_invoke"
    except Exception as exc:
        invoke_error = exc

    try:
        control.click_input()
        return "click_input"
    except RuntimeError as exc:
        _raise_active_desktop_error(exc)
    except Exception as exc:
        if invoke_error is not None:
            raise RuntimeError(f"UIA Invoke失败: {invoke_error}; 鼠标点击失败: {exc}") from exc
        raise


def _raise_active_desktop_error(exc: RuntimeError) -> None:
    message = str(exc)
    if "active desktop" in message or "SetCursorPos" in message:
        raise RuntimeError(
            "当前进程没有可用的活动桌面，无法执行鼠标点击。请在已登录、未锁屏、RDP未断开"
            "的交互式 Windows 桌面中运行服务；如果用任务计划程序启动，请选择“仅当用户登录时运行”。"
        ) from exc
    raise exc


def paste_text(
    text: str,
    clear_existing: bool = True,
    select_wait_seconds: float = 0.01,
    after_wait_seconds: float = 0.02,
) -> None:
    """使用 Windows 剪贴板向当前焦点控件粘贴文本."""

    from pywinauto import keyboard  # type: ignore

    set_clipboard_text(text)
    if clear_existing:
        keyboard.send_keys("^a")
        time.sleep(select_wait_seconds)
    keyboard.send_keys("^v")
    time.sleep(after_wait_seconds)


def send_keys_to_control(control: Any, keys: str, after_wait_seconds: float = 0.05) -> None:
    """聚焦目标窗口后发送键盘按键."""

    from pywinauto import keyboard  # type: ignore

    _safe_method(control, "set_focus")
    keyboard.send_keys(keys)
    time.sleep(after_wait_seconds)


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
    poll_interval_seconds: float = 0.05,
) -> Optional[Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if uia_tree_has_visible_text(root, text, max_depth=8):
            return root
        time.sleep(poll_interval_seconds)
    return None


def uia_tree_has_visible_text(control: Any, text: str, max_depth: Optional[int] = None) -> bool:
    for item, depth in iter_uia_tree(control, max_depth):
        info = uia_control_search_info(item)
        rectangle = info.get("rectangle") or {}
        if info.get("control_type") == "Document":
            continue
        if info.get("visible") is False:
            continue
        if int(rectangle.get("width") or 0) <= 0 or int(rectangle.get("height") or 0) <= 0:
            continue
        if text in info["text_blob"]:
            return True
    return False
