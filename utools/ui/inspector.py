# -*- coding: utf-8 -*-
"""
Inspect controls/components inside a Windows process window.

The preferred backend is UI Automation via pywinauto because apps like WeChat
often draw controls without classic HWND child windows. If pywinauto is not
installed, the code falls back to Win32 window/child-window enumeration.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any, Callable, Dict, Iterable, List, Optional

from utools.components.wechat_pay_order import DEFAULT_PID, DEFAULT_WINDOW_TITLE



def get_process_component_info(
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    backend: str = "auto",
    max_depth: Optional[int] = None,
    include_hidden: bool = True,
    hwnd: Optional[int] = None,
) -> Dict[str, Any]:
    """返回指定进程和标题的窗口组件信息.

    Args:
        pid: 可选目标进程ID. 不传时自动按窗口标题查找进程.
        window_title: 匹配顶级窗口标题的子字符串.
        backend: "auto", "uia", or "win32".
        max_depth: 可选深度限制. 0 表示仅返回顶级窗口.
        include_hidden: 是否包含隐藏/离屏控件.
        hwnd: 可选顶级窗口句柄. 传入时优先按句柄精确匹配.

    Returns:
        包含顶级窗口、组件行和错误的JSON序列化字典.
    """

    if backend not in {"auto", "uia", "win32"}:
        raise ValueError("backend必须是\"auto\", \"uia\"或\"win32\"")
    if pid is None and not window_title and hwnd is None:
        raise ValueError("未指定pid和hwnd时必须提供window_title")

    errors: List[str] = []

    if backend in {"auto", "uia"}:
        try:
            result = _collect_by_uia(pid, window_title, max_depth, include_hidden, hwnd)
            result["errors"] = errors
            return result
        except Exception as exc:  # UIA可能失败，例如缺少依赖项或权限不足
            errors.append(f"uia backend failed: {type(exc).__name__}: {exc}")
            if backend == "uia":
                return _empty_result(pid, window_title, "uia", errors, hwnd)

    try:
        result = _collect_by_win32(pid, window_title, max_depth, include_hidden, hwnd)
        result["errors"] = errors
        return result
    except Exception as exc:  # Win32后端可能失败，例如进程不存在或权限不足
        errors.append(f"win32 backend failed: {type(exc).__name__}: {exc}")
        return _empty_result(pid, window_title, "win32", errors, hwnd)


def find_windows_by_title(window_title: str = DEFAULT_WINDOW_TITLE) -> List[Dict[str, Any]]:
    """按顶级窗口标题查找窗口和对应进程ID."""

    if not window_title:
        raise ValueError("window_title不能为空")

    windows: List[Dict[str, Any]] = []
    for hwnd in _find_win32_top_windows(None, window_title):
        windows.append(
            {
                "pid": _get_window_pid(hwnd),
                "hwnd": hwnd,
                "title": _get_window_text(hwnd),
                "class_name": _get_class_name(hwnd),
                "rectangle": _get_window_rect(hwnd),
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "enabled": bool(user32.IsWindowEnabled(hwnd)),
            }
        )
    return windows


def _collect_by_uia(
    pid: Optional[int],
    window_title: str,
    max_depth: Optional[int],
    include_hidden: bool,
    hwnd: Optional[int],
) -> Dict[str, Any]:
    from pywinauto import Desktop  # type: ignore

    desktop = Desktop(backend="uia")
    top_windows = _find_uia_top_windows(desktop.windows(), pid, window_title, hwnd)
    if not top_windows:
        pid_text = f"PID为{pid}，" if pid is not None else ""
        raise RuntimeError(
            f"未找到{pid_text}句柄为{hwnd}，标题包含\"{window_title}\"的顶级UIA窗口."
        )

    components: List[Dict[str, Any]] = []
    top_window_infos: List[Dict[str, Any]] = []

    for root_index, root in enumerate(top_windows):
        root_info = _uia_control_to_info(root, root_index, 0, str(root_index))
        top_window_infos.append(root_info)
        _walk_uia_tree(
            root,
            root_index=root_index,
            depth=0,
            path=str(root_index),
            max_depth=max_depth,
            include_hidden=include_hidden,
            rows=components,
        )

    return {
        "query": {
            "pid": pid,
            "hwnd": hwnd,
            "matched_pids": sorted(
                {
                    item["process_id"]
                    for item in top_window_infos
                    if item.get("process_id") is not None
                }
            ),
            "window_title": window_title,
            "backend": "uia",
            "max_depth": max_depth,
            "include_hidden": include_hidden,
        },
        "backend": "uia",
        "top_windows": top_window_infos,
        "component_count": len(components),
        "components": components,
    }


def _find_uia_top_windows(
    windows: Iterable[Any],
    pid: Optional[int],
    window_title: str,
    hwnd: Optional[int] = None,
) -> List[Any]:
    matched: List[Any] = []
    fallback_by_pid: List[Any] = []

    for window in windows:
        info = getattr(window, "element_info", window)
        process_id = _safe_get(lambda: info.process_id)
        handle = _safe_get(lambda: info.handle)
        title = _safe_get(lambda: info.name, "") or _safe_method(
            window, "window_text", ""
        )
        if hwnd is not None and handle != hwnd:
            continue
        if pid is not None and process_id != pid:
            continue
        fallback_by_pid.append(window)
        if not window_title or window_title in title:
            matched.append(window)

    result = matched if pid is None else matched or fallback_by_pid

    def title_aware_sort_key(window: Any) -> tuple[int, int, int, int]:
        info = getattr(window, "element_info", window)
        title = str(
            _safe_get(lambda: info.name, "")
            or _safe_method(window, "window_text", "")
            or ""
        )
        return (0 if title.strip() == window_title.strip() else 1, *_uia_window_sort_key(window))

    return sorted(result, key=title_aware_sort_key)


def _uia_window_sort_key(window: Any) -> tuple[int, int, int]:
    info = getattr(window, "element_info", window)
    rectangle = _rect_to_dict(_safe_get(lambda: info.rectangle))
    visible = _safe_method(window, "is_visible")
    width = int((rectangle or {}).get("width") or 0)
    height = int((rectangle or {}).get("height") or 0)
    left = int((rectangle or {}).get("left") or 0)
    top = int((rectangle or {}).get("top") or 0)
    normal_position = left > -10000 and top > -10000
    usable_area = width * height
    return (
        0 if visible else 1,
        0 if normal_position and usable_area > 0 else 1,
        -usable_area,
    )


def _walk_uia_tree(
    control: Any,
    root_index: int,
    depth: int,
    path: str,
    max_depth: Optional[int],
    include_hidden: bool,
    rows: List[Dict[str, Any]],
) -> None:
    info = _uia_control_to_info(control, root_index, depth, path)
    if include_hidden or info.get("visible") is not False:
        rows.append(info)

    if max_depth is not None and depth >= max_depth:
        return

    children = _safe_method(control, "children", []) or []
    for index, child in enumerate(children):
        _walk_uia_tree(
            child,
            root_index=root_index,
            depth=depth + 1,
            path=f"{path}/{index}",
            max_depth=max_depth,
            include_hidden=include_hidden,
            rows=rows,
        )


def _uia_control_to_info(
    control: Any,
    root_index: int,
    depth: int,
    path: str,
) -> Dict[str, Any]:
    element = getattr(control, "element_info", control)
    rectangle = _safe_get(lambda: element.rectangle)
    children = _safe_method(control, "children", []) or []
    name = _safe_get(lambda: element.name, "") or _safe_method(control, "window_text", "")

    return {
        "backend": "uia",
        "root_index": root_index,
        "depth": depth,
        "path": path,
        "name": name,
        "text": _safe_method(control, "window_text", ""),
        "control_type": _safe_get(lambda: element.control_type),
        "automation_id": _safe_get(lambda: element.automation_id),
        "class_name": _safe_get(lambda: element.class_name),
        "hwnd": _safe_get(lambda: element.handle),
        "process_id": _safe_get(lambda: element.process_id),
        "rectangle": _rect_to_dict(rectangle),
        "visible": _safe_method(control, "is_visible"),
        "enabled": _safe_method(control, "is_enabled"),
        "children_count": len(children),
        "value": _safe_method(control, "get_value"),
    }


def _collect_by_win32(
    pid: Optional[int],
    window_title: str,
    max_depth: Optional[int],
    include_hidden: bool,
    hwnd: Optional[int],
) -> Dict[str, Any]:
    top_hwnds = _find_win32_top_windows(pid, window_title, hwnd)
    if not top_hwnds:
        pid_text = f"pid={pid}, " if pid is not None else ""
        raise RuntimeError(
            f'No top-level Win32 window found for {pid_text}hwnd={hwnd}, title contains "{window_title}".'
        )

    components: List[Dict[str, Any]] = []
    top_window_infos: List[Dict[str, Any]] = []

    for root_index, hwnd in enumerate(top_hwnds):
        top_window_infos.append(_win32_hwnd_to_info(hwnd, root_index, 0, str(root_index)))
        _walk_win32_tree(
            hwnd,
            root_index=root_index,
            depth=0,
            path=str(root_index),
            max_depth=max_depth,
            include_hidden=include_hidden,
            rows=components,
        )

    return {
        "query": {
            "pid": pid,
            "hwnd": hwnd,
            "matched_pids": sorted(
                {
                    item["process_id"]
                    for item in top_window_infos
                    if item.get("process_id") is not None
                }
            ),
            "window_title": window_title,
            "backend": "win32",
            "max_depth": max_depth,
            "include_hidden": include_hidden,
        },
        "backend": "win32",
        "top_windows": top_window_infos,
        "component_count": len(components),
        "components": components,
    }


def _find_win32_top_windows(
    pid: Optional[int],
    window_title: str,
    hwnd: Optional[int] = None,
) -> List[int]:
    matched: List[int] = []
    fallback_by_pid: List[int] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        window_pid = _get_window_pid(hwnd)
        if target_hwnd is not None and hwnd != target_hwnd:
            return True
        if pid is not None and window_pid != pid:
            return True

        title = _get_window_text(hwnd)
        fallback_by_pid.append(hwnd)
        if window_title in title:
            matched.append(hwnd)
        return True

    target_hwnd = hwnd
    _enum_windows(callback)
    return matched if pid is None else matched or fallback_by_pid


def _walk_win32_tree(
    hwnd: int,
    root_index: int,
    depth: int,
    path: str,
    max_depth: Optional[int],
    include_hidden: bool,
    rows: List[Dict[str, Any]],
) -> None:
    info = _win32_hwnd_to_info(hwnd, root_index, depth, path)
    if include_hidden or info.get("visible") is not False:
        rows.append(info)

    if max_depth is not None and depth >= max_depth:
        return

    child = user32.GetWindow(hwnd, GW_CHILD)
    index = 0
    while child:
        _walk_win32_tree(
            child,
            root_index=root_index,
            depth=depth + 1,
            path=f"{path}/{index}",
            max_depth=max_depth,
            include_hidden=include_hidden,
            rows=rows,
        )
        child = user32.GetWindow(child, GW_HWNDNEXT)
        index += 1


def _win32_hwnd_to_info(
    hwnd: int,
    root_index: int,
    depth: int,
    path: str,
) -> Dict[str, Any]:
    return {
        "backend": "win32",
        "root_index": root_index,
        "depth": depth,
        "path": path,
        "name": _get_window_text(hwnd),
        "text": _get_window_text(hwnd),
        "control_type": "Window",
        "automation_id": None,
        "class_name": _get_class_name(hwnd),
        "hwnd": hwnd,
        "process_id": _get_window_pid(hwnd),
        "rectangle": _get_window_rect(hwnd),
        "visible": bool(user32.IsWindowVisible(hwnd)),
        "enabled": bool(user32.IsWindowEnabled(hwnd)),
        "children_count": _count_direct_win32_children(hwnd),
        "value": None,
    }


def _empty_result(
    pid: Optional[int],
    window_title: str,
    backend: str,
    errors: List[str],
    hwnd: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "query": {
            "pid": pid,
            "hwnd": hwnd,
            "window_title": window_title,
            "backend": backend,
        },
        "backend": backend,
        "top_windows": [],
        "component_count": 0,
        "components": [],
        "errors": errors,
    }


def _safe_get(func: Callable[[], Any], default: Any = None) -> Any:
    try:
        return func()
    except Exception:
        return default


def _safe_method(
    obj: Any,
    method_name: str,
    default: Any = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return default
    try:
        return method(*args, **kwargs)
    except Exception:
        return default


def _rect_to_dict(rectangle: Any) -> Optional[Dict[str, int]]:
    if rectangle is None:
        return None

    left = _safe_get(lambda: rectangle.left)
    top = _safe_get(lambda: rectangle.top)
    right = _safe_get(lambda: rectangle.right)
    bottom = _safe_get(lambda: rectangle.bottom)
    if None in {left, top, right, bottom}:
        return None

    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": int(right - left),
        "height": int(bottom - top),
    }


user32 = ctypes.WinDLL("user32", use_last_error=True)

GW_HWNDNEXT = 2
GW_CHILD = 5

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int,
]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetClassNameW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int,
]
user32.GetClassNameW.restype = ctypes.c_int

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsWindowEnabled.argtypes = [wintypes.HWND]
user32.IsWindowEnabled.restype = wintypes.BOOL


def _enum_windows(callback: Callable[[int, int], bool]) -> None:
    c_callback = WNDENUMPROC(callback)
    if not user32.EnumWindows(c_callback, 0):
        raise ctypes.WinError(ctypes.get_last_error())


def _get_window_pid(hwnd: int) -> int:
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    return int(process_id.value)


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def _count_direct_win32_children(hwnd: int) -> int:
    count = 0
    child = user32.GetWindow(hwnd, GW_CHILD)
    while child:
        count += 1
        child = user32.GetWindow(child, GW_HWNDNEXT)
    return count
