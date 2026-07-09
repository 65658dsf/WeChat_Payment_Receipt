# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional

from utools.components.wechat_pay_order import (
    DEFAULT_PID,
    DEFAULT_WINDOW_TITLE,
    WECHAT_PAY_ORDER,
)
from utools.ui.screenshot import capture_relative_crop
from utools.ui.inspector import _safe_get, _safe_method, _uia_control_to_info
from utools.ui.operator import (
    click_relative,
    click_screen_point,
    enable_fast_timings,
    find_first_uia_top_window,
    find_uia_click_target,
    iter_uia_tree,
    paste_text,
    uia_text_blob,
    uia_tree_has_visible_text,
    wait_for_visible_uia_text,
)


AMOUNT_KEYPAD_POINTS = {
    "1": (0.13, 0.73),
    "2": (0.37, 0.73),
    "3": (0.60, 0.73),
    "4": (0.13, 0.80),
    "5": (0.37, 0.80),
    "6": (0.60, 0.80),
    "7": (0.13, 0.88),
    "8": (0.37, 0.88),
    "9": (0.60, 0.88),
    "0": (0.25, 0.96),
    ".": (0.60, 0.96),
}
AMOUNT_KEYPAD_BACKSPACE = (0.84, 0.73)


def open_create_pay_order_page(
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """打开“创建收款单”界面，返回点击动作和目标窗口信息."""

    _root, action_result = _open_create_pay_order_page(
        pid=pid,
        window_title=window_title,
        timeout_seconds=timeout_seconds,
    )
    return action_result


def generate_pay_order(
    amount: str,
    order_no: str,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    timeout_seconds: float = 8.0,
    save_qr_code: bool = True,
    qr_output_dir: str = "outputs",
    return_to_wait_page: bool = True,
    wait_paid_and_close: bool = False,
    wait_paid_timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """创建收款单、保存收款码，并可等待支付完成后关闭收款单."""

    enable_fast_timings()
    _require_non_empty(amount, "金额")
    _require_non_empty(order_no, "订单号")

    root, action_result = _open_create_pay_order_page(
        pid=pid,
        window_title=window_title,
        timeout_seconds=timeout_seconds,
    )
    action_result["filled"] = fill_create_pay_order_fields(
        root=root,
        amount=amount,
        order_no=order_no,
    )
    action_result["created"] = submit_create_pay_order(root, timeout_seconds)
    if save_qr_code:
        action_result["qr_code"] = generate_and_capture_qr_code(
            root=root,
            order_no=order_no,
            output_dir=qr_output_dir,
            timeout_seconds=timeout_seconds,
        )
        if return_to_wait_page:
            action_result["return_wait_page"] = return_to_wait_payment_page(
                root=root,
                timeout_seconds=timeout_seconds,
            )
            if wait_paid_and_close:
                action_result["payment"] = wait_paid_then_close_pay_order(
                    root=root,
                    order_no=order_no,
                    pid=pid,
                    window_title=window_title,
                    timeout_seconds=wait_paid_timeout_seconds,
                )
                print("支付成功", flush=True)
    if save_qr_code and return_to_wait_page and wait_paid_and_close:
        action_result["message"] = "已创建收款单，已生成收款码截图，已收款并关闭/删除收款单."
    elif save_qr_code and return_to_wait_page:
        action_result["message"] = "已创建收款单，已生成收款码截图，并返回主界面等待付款."
    elif save_qr_code:
        action_result["message"] = "已创建收款单，并生成收款码截图."
    else:
        action_result["message"] = "已创建收款单."
    return action_result


def fill_create_pay_order_fields(root: Any, amount: str, order_no: str) -> Dict[str, Any]:
    """填写创建收款单界面的金额和收款说明."""

    enable_fast_timings()
    components = WECHAT_PAY_ORDER

    amount_point = _fill_amount_by_keypad(
        root,
        str(amount),
    )

    description_point = click_relative(
        root,
        components.description_input_x_ratio,
        components.description_input_y_ratio,
    )
    paste_text(
        str(order_no),
        clear_existing=True,
        select_wait_seconds=components.paste_select_wait_seconds,
        after_wait_seconds=components.paste_after_wait_seconds,
    )

    return {
        "amount": str(amount),
        "order_no": str(order_no),
        "amount_click_point": {"x": amount_point[0], "y": amount_point[1]},
        "description_click_point": {
            "x": description_point[0],
            "y": description_point[1],
        },
    }


def submit_create_pay_order(root: Any, timeout_seconds: float = 8.0) -> Dict[str, Any]:
    """点击“创建”，等待已创建弹窗出现."""

    components = WECHAT_PAY_ORDER
    create_point = click_relative(
        root,
        components.create_button_x_ratio,
        components.create_button_y_ratio,
    )
    created_root = wait_for_visible_uia_text(
        root=root,
        text=components.created_dialog_title,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if created_root is None:
        raise TimeoutError(f"点击创建后未在{timeout_seconds}秒内看到“{components.created_dialog_title}”.")

    return {
        "created": True,
        "create_click_point": {"x": create_point[0], "y": create_point[1]},
    }


def generate_and_capture_qr_code(
    root: Any,
    order_no: str,
    output_dir: str = "outputs",
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """点击“生成收款码”，并裁剪保存中间白色收款码区域."""

    components = WECHAT_PAY_ORDER
    generate_button = find_uia_click_target(
        root,
        text=components.generate_qr_button_text,
        max_depth=10,
    )
    if generate_button is not None:
        generate_button_info = _uia_control_to_info(generate_button, 0, 0, "target")
        generate_button.click_input()
        generate_click_point = None
    else:
        generate_button_info = None
        point = click_relative(
            root,
            components.generate_qr_button_x_ratio,
            components.generate_qr_button_y_ratio,
        )
        generate_click_point = {"x": point[0], "y": point[1]}

    share_root = wait_for_visible_uia_text(
        root=root,
        text=components.generated_share_title,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if share_root is None:
        raise TimeoutError(
            f"点击“{components.generate_qr_button_text}”后未在{timeout_seconds}秒内进入“{components.generated_share_title}”."
        )

    output_path = _make_qr_output_path(order_no, output_dir)
    capture_result = capture_relative_crop(
        control=share_root,
        output_path=output_path,
        left_ratio=components.qr_card_left_ratio,
        top_ratio=components.qr_card_top_ratio,
        right_ratio=components.qr_card_right_ratio,
        bottom_ratio=components.qr_card_bottom_ratio,
    )
    return {
        "generated": True,
        "button": generate_button_info,
        "generate_click_point": generate_click_point,
        **capture_result,
    }


def return_to_wait_payment_page(
    root: Any,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """从生成分享图页面返回两次，等待回到主界面订单等待付款状态."""

    components = WECHAT_PAY_ORDER
    back_click_points = []
    for _ in range(components.return_back_click_count):
        point = click_relative(
            root,
            components.return_back_button_x_ratio,
            components.return_back_button_y_ratio,
        )
        back_click_points.append({"x": point[0], "y": point[1]})
        time.sleep(components.return_back_after_click_wait_seconds)

    wait_root = wait_for_visible_uia_text(
        root=root,
        text=components.wait_payment_status_text,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if wait_root is None:
        raise TimeoutError(
            f"返回主界面后未在{timeout_seconds}秒内看到“{components.wait_payment_status_text}”."
        )

    return {
        "returned": True,
        "back_click_count": components.return_back_click_count,
        "back_click_points": back_click_points,
        "wait_text": components.wait_payment_status_text,
    }


def wait_paid_then_close_pay_order(
    root: Any,
    order_no: str = "",
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """每秒刷新主界面，发现已支付后进入详情并关闭收款单."""

    components = WECHAT_PAY_ORDER
    timeout = timeout_seconds
    deadline = None if timeout is None else time.time() + timeout
    refresh_count = 0
    last_refresh_result: Optional[Dict[str, Any]] = None
    paid_card_point: Optional[tuple[int, int]] = None
    last_status: Optional[Dict[str, Any]] = None

    while True:
        root = _reacquire_pay_order_root(root, pid, window_title)
        last_status = _read_order_payment_status(root, str(order_no))
        if last_status["status"] == "unknown":
            root, last_status = wait_order_status_loaded(
                root=root,
                order_no=order_no,
                pid=pid,
                window_title=window_title,
                timeout_seconds=components.order_status_load_timeout_seconds,
            )
        if last_status["status"] == "paid":
            paid_card_point = last_status.get("click_point")
            break
        if last_status["status"] != "unpaid":
            raise RuntimeError(f"无法识别订单状态: {last_status}")
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(
                f"等待付款超时，{timeout}秒内未看到“{components.paid_status_text}”."
            )
        refresh_started_at = time.time()
        root, last_refresh_result = refresh_wait_payment_page(
            root=root,
            order_no=order_no,
            pid=pid,
            window_title=window_title,
        )
        refresh_count += 1
        refresh_elapsed = time.time() - refresh_started_at
        time.sleep(max(0.0, components.payment_refresh_interval_seconds - refresh_elapsed))

    if paid_card_point is not None:
        paid_card_point = click_screen_point(*paid_card_point)
    else:
        paid_card_point = _click_text_or_relative(
            root,
            text=components.paid_status_text,
            x_ratio=components.paid_card_x_ratio,
            y_ratio=components.paid_card_y_ratio,
    )
    time.sleep(components.after_open_paid_card_wait_seconds)
    root = _reacquire_pay_order_root(root, pid, window_title)

    detail_root = wait_for_visible_uia_text(
        root=root,
        text=components.payment_detail_title,
        timeout_seconds=8.0,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if detail_root is None:
        raise TimeoutError(f"点击已支付卡片后未进入“{components.payment_detail_title}”.")

    more_action_point = _click_text_or_relative(
        root,
        text=components.more_action_text,
        x_ratio=components.more_action_x_ratio,
        y_ratio=components.more_action_y_ratio,
    )
    time.sleep(components.after_more_action_wait_seconds)

    close_menu_root = wait_for_visible_uia_text(
        root=root,
        text=components.close_pay_order_text,
        timeout_seconds=8.0,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if close_menu_root is None:
        raise TimeoutError(f"点击更多操作后未看到“{components.close_pay_order_text}”.")

    close_point = _click_text_or_relative(
        root,
        text=components.close_pay_order_text,
        x_ratio=components.close_pay_order_x_ratio,
        y_ratio=components.close_pay_order_y_ratio,
    )

    confirm_close_root = wait_for_visible_uia_text(
        root=root,
        text=components.confirm_close_pay_order_text,
        timeout_seconds=8.0,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if confirm_close_root is None:
        raise TimeoutError(f"点击关闭收款单后未看到“{components.confirm_close_pay_order_text}”.")

    confirm_close_point = _click_text_or_relative(
        root,
        text=components.confirm_close_pay_order_text,
        x_ratio=components.confirm_close_pay_order_x_ratio,
        y_ratio=components.confirm_close_pay_order_y_ratio,
    )
    time.sleep(components.after_confirm_close_wait_seconds)

    more_action_after_close_point = _click_text_or_relative(
        root,
        text=components.more_action_text,
        x_ratio=components.more_action_x_ratio,
        y_ratio=components.more_action_y_ratio,
    )
    time.sleep(components.after_more_action_wait_seconds)

    delete_menu_root = wait_for_visible_uia_text(
        root=root,
        text=components.delete_pay_order_text,
        timeout_seconds=8.0,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if delete_menu_root is None:
        raise TimeoutError(f"确认关闭后再次点击更多操作，未看到“{components.delete_pay_order_text}”.")

    delete_point = _click_text_or_relative(
        root,
        text=components.delete_pay_order_text,
        x_ratio=components.delete_pay_order_x_ratio,
        y_ratio=components.delete_pay_order_y_ratio,
    )
    time.sleep(components.after_delete_pay_order_wait_seconds)

    confirm_delete_root = wait_for_visible_uia_text(
        root=root,
        text=components.confirm_delete_pay_order_text,
        timeout_seconds=8.0,
        poll_interval_seconds=components.wait_poll_interval_seconds,
    )
    if confirm_delete_root is None:
        raise TimeoutError(f"点击删除收款单后未看到“{components.confirm_delete_pay_order_text}”.")

    confirm_delete_point = _click_text_or_relative(
        root,
        text=components.confirm_delete_pay_order_text,
        x_ratio=components.confirm_delete_pay_order_x_ratio,
        y_ratio=components.confirm_delete_pay_order_y_ratio,
    )
    time.sleep(components.after_confirm_delete_wait_seconds)

    return {
        "paid": True,
        "closed": True,
        "deleted": True,
        "refresh_count": refresh_count,
        "last_refresh": last_refresh_result,
        "last_status": last_status,
        "paid_card_click_point": {"x": paid_card_point[0], "y": paid_card_point[1]},
        "more_action_click_point": {"x": more_action_point[0], "y": more_action_point[1]},
        "close_click_point": {"x": close_point[0], "y": close_point[1]},
        "confirm_close_click_point": {
            "x": confirm_close_point[0],
            "y": confirm_close_point[1],
        },
        "more_action_after_close_click_point": {
            "x": more_action_after_close_point[0],
            "y": more_action_after_close_point[1],
        },
        "delete_click_point": {"x": delete_point[0], "y": delete_point[1]},
        "confirm_delete_click_point": {
            "x": confirm_delete_point[0],
            "y": confirm_delete_point[1],
        },
    }


def refresh_wait_payment_page(
    root: Any,
    order_no: str = "",
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> tuple[Any, Dict[str, Any]]:
    """通过小程序右上角菜单点击“重新进入小程序”刷新主界面."""

    components = WECHAT_PAY_ORDER
    root = _reacquire_pay_order_root(root, pid, window_title)
    menu_point = click_relative(
        root,
        components.mini_program_menu_x_ratio,
        components.mini_program_menu_y_ratio,
    )
    time.sleep(components.refresh_menu_after_click_wait_seconds)

    reenter_point = _click_text_or_relative(
        root,
        text=components.reenter_mini_program_text,
        x_ratio=components.reenter_mini_program_x_ratio,
        y_ratio=components.reenter_mini_program_y_ratio,
    )
    time.sleep(components.refresh_reenter_after_click_wait_seconds)
    refreshed_root = _reacquire_pay_order_root(root, None, window_title)
    refreshed_root, loaded_status = wait_order_status_loaded(
        root=refreshed_root,
        order_no=order_no,
        pid=None,
        window_title=window_title,
        timeout_seconds=components.order_status_load_timeout_seconds,
    )

    return refreshed_root, {
        "menu_click_point": {"x": menu_point[0], "y": menu_point[1]},
        "reenter_click_point": {"x": reenter_point[0], "y": reenter_point[1]},
        "loaded_status": loaded_status,
    }


def wait_order_status_loaded(
    root: Any,
    order_no: str = "",
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    timeout_seconds: float = 8.0,
) -> tuple[Any, Dict[str, Any]]:
    """等待主界面加载出目标订单的未支付或已支付状态."""

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        root = _reacquire_pay_order_root(root, pid, window_title)
        status = _read_order_payment_status(root, order_no)
        if status["status"] in {"unpaid", "paid"}:
            return root, status
        time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
    raise TimeoutError(
        f"重新进入小程序后未在{timeout_seconds}秒内读取到订单状态"
        f"（{WECHAT_PAY_ORDER.wait_payment_status_text}/{WECHAT_PAY_ORDER.paid_status_text}）."
    )


def _reacquire_pay_order_root(
    current_root: Any,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> Any:
    from pywinauto import Desktop  # type: ignore

    enable_fast_timings()
    desktop = Desktop(backend="uia")
    try:
        return find_first_uia_top_window(desktop, pid, window_title)
    except Exception:
        if pid is not None:
            try:
                return find_first_uia_top_window(desktop, None, window_title)
            except Exception:
                pass
        if _control_has_valid_rectangle(current_root):
            return current_root
        raise


def _control_has_valid_rectangle(control: Any) -> bool:
    if control is None:
        return False
    try:
        info = _uia_control_to_info(control, 0, 0, "valid-root")
        rectangle = info.get("rectangle") or {}
        return int(rectangle.get("width") or 0) > 0 and int(rectangle.get("height") or 0) > 0
    except Exception:
        return False


def _read_order_payment_status(root: Any, order_no: str) -> Dict[str, Any]:
    components = WECHAT_PAY_ORDER
    paid_point = _find_order_status_card_click_point(
        root,
        order_no,
        components.paid_status_text,
    )
    if paid_point is not None:
        return {
            "status": "paid",
            "status_text": components.paid_status_text,
            "click_point": paid_point,
        }

    unpaid_point = _find_order_status_card_click_point(
        root,
        order_no,
        components.wait_payment_status_text,
    )
    if unpaid_point is not None:
        return {
            "status": "unpaid",
            "status_text": components.wait_payment_status_text,
            "click_point": unpaid_point,
        }

    return {
        "status": "unknown",
        "status_text": "",
        "click_point": None,
    }


def _find_paid_order_card_click_point(root: Any, order_no: str) -> Optional[tuple[int, int]]:
    return _find_order_status_card_click_point(
        root,
        order_no,
        WECHAT_PAY_ORDER.paid_status_text,
    )


def _find_order_status_card_click_point(
    root: Any,
    order_no: str,
    status_text: str,
) -> Optional[tuple[int, int]]:
    status_rects = _find_visible_text_rects(root, status_text)
    if not status_rects:
        return None
    if not order_no:
        return _rect_center(status_rects[0])

    order_rects = _find_visible_text_rects(root, order_no)
    for order_rect in order_rects:
        for status_rect in status_rects:
            if _looks_like_same_order_card(order_rect, status_rect):
                return _rect_center(status_rect)
    return None


def _find_visible_text_rects(root: Any, text: str) -> list[Dict[str, int]]:
    rects: list[Dict[str, int]] = []
    for item, depth in iter_uia_tree(root, max_depth=8):
        info = _uia_control_to_info(item, 0, depth, "text-rect")
        rectangle = info.get("rectangle") or {}
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        if info.get("control_type") == "Document":
            continue
        if info.get("visible") is False:
            continue
        if width <= 0 or height <= 0:
            continue
        if text not in uia_text_blob(item):
            continue
        rects.append(
            {
                "left": int(rectangle.get("left") or 0),
                "top": int(rectangle.get("top") or 0),
                "right": int(rectangle.get("right") or 0),
                "bottom": int(rectangle.get("bottom") or 0),
                "width": width,
                "height": height,
            }
        )
    return rects


def _looks_like_same_order_card(
    order_rect: Dict[str, int],
    paid_rect: Dict[str, int],
) -> bool:
    vertical_distance = paid_rect["top"] - order_rect["top"]
    horizontal_distance = paid_rect["left"] - order_rect["left"]
    if vertical_distance < -30 or vertical_distance > 170:
        return False
    if horizontal_distance < -120 or horizontal_distance > 260:
        return False
    return True


def _rect_center(rectangle: Dict[str, int]) -> tuple[int, int]:
    return (
        rectangle["left"] + rectangle["width"] // 2,
        rectangle["top"] + rectangle["height"] // 2,
    )


def _click_text_or_relative(
    root: Any,
    text: str,
    x_ratio: float,
    y_ratio: float,
) -> tuple[int, int]:
    target = find_uia_click_target(root, text=text, max_depth=10)
    if target is not None:
        target_info = _uia_control_to_info(target, 0, 0, "target")
        rectangle = target_info.get("rectangle") or {}
        left = int(rectangle.get("left") or 0)
        top = int(rectangle.get("top") or 0)
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        if width > 0 and height > 0:
            try:
                target.click_input()
                return left + width // 2, top + height // 2
            except Exception:
                pass

    return click_relative(root, x_ratio, y_ratio)


def _fill_amount_by_keypad(root: Any, amount: str) -> tuple[int, int]:
    components = WECHAT_PAY_ORDER
    _validate_amount_text(amount)

    amount_point = click_relative(
        root,
        components.amount_input_x_ratio,
        components.amount_input_y_ratio,
    )

    for _ in range(components.amount_clear_backspace_count):
        click_relative(root, *AMOUNT_KEYPAD_BACKSPACE)

    for char in amount:
        click_relative(root, *AMOUNT_KEYPAD_POINTS[char])

    return amount_point


def _validate_amount_text(amount: str) -> None:
    allowed = set(AMOUNT_KEYPAD_POINTS)
    invalid = [char for char in amount if char not in allowed]
    if invalid:
        raise ValueError(f"金额只能包含数字和小数点，非法字符: {''.join(invalid)}")
    if amount.count(".") > 1:
        raise ValueError("金额最多只能包含一个小数点.")
    if not any(char.isdigit() for char in amount):
        raise ValueError("金额至少需要包含一个数字.")


def _open_create_pay_order_page(
    pid: Optional[int],
    window_title: str,
    timeout_seconds: float,
) -> tuple[Any, Dict[str, Any]]:
    from pywinauto import Desktop  # type: ignore

    enable_fast_timings()
    desktop = Desktop(backend="uia")
    root = find_first_uia_top_window(desktop, pid, window_title)
    root_info = _uia_control_to_info(root, 0, 0, "0")
    process_id = root_info.get("process_id")
    create_title = WECHAT_PAY_ORDER.create_pay_order_title
    create_button_text = WECHAT_PAY_ORDER.create_pay_order_button_text

    _safe_method(root, "set_focus")
    if uia_tree_has_visible_text(root, create_title, max_depth=8):
        return root, {
            "opened": True,
            "already_open": True,
            "pid": process_id,
            "window": root_info,
            "message": f"当前已经在“{create_title}”界面.",
        }

    button = find_uia_click_target(
        root,
        text=create_button_text,
        max_depth=10,
    )
    if button is None:
        raise RuntimeError(f"未找到“{create_button_text}”按钮.")

    button_info = _uia_control_to_info(button, 0, 0, "target")
    try:
        button.click_input()
    except Exception as exc:
        raise RuntimeError(f"找到“{create_button_text}”，但点击失败: {exc}") from exc

    opened_root = wait_for_visible_uia_text(
        root=root,
        text=create_title,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=WECHAT_PAY_ORDER.wait_poll_interval_seconds,
    )
    if opened_root is None:
        raise TimeoutError(f"点击后未在{timeout_seconds}秒内进入“{create_title}”界面.")

    return opened_root, {
        "opened": True,
        "already_open": False,
        "pid": _safe_get(lambda: opened_root.element_info.process_id, process_id),
        "window": _uia_control_to_info(opened_root, 0, 0, "0"),
        "clicked": button_info,
        "message": f"已点击“{create_button_text}”，进入“{create_title}”界面.",
    }


def _require_non_empty(value: str, label: str) -> None:
    if str(value).strip() == "":
        raise ValueError(f"{label}不能为空.")


def _make_qr_output_path(order_no: str, output_dir: str) -> str:
    safe_order_no = re.sub(r'[<>:"/\\|?*\s]+', "_", str(order_no)).strip("._")
    if not safe_order_no:
        safe_order_no = "pay_order"
    return os.path.join(output_dir, f"收款码_{safe_order_no}.png")
