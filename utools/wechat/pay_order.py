# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, Optional

from utools.components.wechat_pay_order import (
    DEFAULT_PID,
    DEFAULT_WINDOW_TITLE,
    WECHAT_PAY_ORDER,
)
from utools.ui.screenshot import (
    capture_control_visual_probe,
    capture_relative_crop,
    compare_control_visual_probes,
)
from utools.ui.inspector import _safe_get, _safe_method, _uia_control_to_info
from utools.ui.operator import (
    click_relative,
    click_screen_point,
    enable_fast_timings,
    find_first_uia_top_window,
    find_uia_click_target,
    invoke_or_click,
    iter_uia_tree,
    paste_text,
    uia_control_search_info,
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


class PayOrderWindowUnavailableError(RuntimeError):
    """微信收款单窗口在短暂重建后仍无法重新获取."""


def _record_timing(
    timings: Dict[str, float],
    name: str,
    started_at: float,
) -> float:
    duration = round(time.perf_counter() - started_at, 3)
    timings[name] = duration
    return duration


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

    workflow_started_at = time.perf_counter()
    timings: Dict[str, float] = {}
    enable_fast_timings()
    _require_non_empty(amount, "金额")
    _require_non_empty(order_no, "订单号")

    stage_started_at = time.perf_counter()
    root, action_result = _open_create_pay_order_page(
        pid=pid,
        window_title=window_title,
        timeout_seconds=timeout_seconds,
    )
    timings["open_create_page"] = round(time.perf_counter() - stage_started_at, 3)
    stage_started_at = time.perf_counter()
    action_result["filled"] = fill_create_pay_order_fields(
        root=root,
        amount=amount,
        order_no=order_no,
    )
    timings["fill_fields"] = round(time.perf_counter() - stage_started_at, 3)
    stage_started_at = time.perf_counter()
    action_result["created"] = submit_create_pay_order(root, timeout_seconds)
    timings["submit_create"] = round(time.perf_counter() - stage_started_at, 3)
    if save_qr_code:
        stage_started_at = time.perf_counter()
        action_result["qr_code"] = generate_and_capture_qr_code(
            root=root,
            order_no=order_no,
            output_dir=qr_output_dir,
            timeout_seconds=timeout_seconds,
            pid=pid,
            window_title=window_title,
        )
        timings["capture_qr_code"] = round(time.perf_counter() - stage_started_at, 3)
        if return_to_wait_page:
            stage_started_at = time.perf_counter()
            action_result["return_wait_page"] = return_to_wait_payment_page(
                root=root,
                order_no=order_no,
                timeout_seconds=timeout_seconds,
                pid=pid,
                window_title=window_title,
            )
            timings["return_wait_page"] = round(time.perf_counter() - stage_started_at, 3)
            if wait_paid_and_close:
                action_result["payment"] = wait_paid_then_close_pay_order(
                    root=root,
                    order_no=order_no,
                    pid=pid,
                    window_title=window_title,
                    timeout_seconds=wait_paid_timeout_seconds,
                    timings_seconds=timings,
                )
                if action_result["payment"].get("paid"):
                    print("支付成功", flush=True)
                else:
                    print(
                        f"支付失败，已关闭并删除收款单: "
                        f"{action_result['payment'].get('failure_reason')}",
                        flush=True,
                    )
    if save_qr_code and return_to_wait_page and wait_paid_and_close:
        payment = action_result.get("payment") or {}
        action_result["message"] = (
            "已创建收款单，已生成收款码截图，已收款并关闭/删除收款单."
            if payment.get("paid")
            else "已创建收款单，付款超时后已关闭/删除收款单."
        )
    elif save_qr_code and return_to_wait_page:
        action_result["message"] = "已创建收款单，已生成收款码截图，并返回主界面等待付款."
    elif save_qr_code:
        action_result["message"] = "已创建收款单，并生成收款码截图."
    else:
        action_result["message"] = "已创建收款单."
    timings["total"] = round(time.perf_counter() - workflow_started_at, 3)
    action_result["timings_seconds"] = timings
    return action_result


def fill_create_pay_order_fields(root: Any, amount: str, order_no: str) -> Dict[str, Any]:
    """填写创建收款单界面的金额和收款说明."""

    enable_fast_timings()
    components = WECHAT_PAY_ORDER

    amount_point = _fill_amount_by_keypad(
        root,
        str(amount),
    )

    if components.fast_input_coordinate_mode:
        description_point = click_relative(
            root,
            components.description_input_x_ratio,
            components.description_input_y_ratio,
        )
    else:
        description_point = _click_labeled_input_or_relative(
            root,
            components.description_input_text,
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
    create_point = _click_text_or_relative(
        root,
        text=components.create_button_text,
        x_ratio=components.create_button_x_ratio,
        y_ratio=components.create_button_y_ratio,
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
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> Dict[str, Any]:
    """点击“生成收款码”，并裁剪保存中间白色收款码区域."""

    components = WECHAT_PAY_ORDER
    retry_count = max(1, components.generate_qr_retry_count)
    share_page_timeout = min(timeout_seconds, components.generate_qr_page_timeout_seconds)
    retry_errors: list[str] = []
    generate_button_info: Optional[Dict[str, Any]] = None
    generate_click_point: Optional[Dict[str, int]] = None
    generate_click_method = ""
    share_root: Any = None

    for attempt in range(1, retry_count + 1):
        try:
            root = _reacquire_pay_order_root(root, pid, window_title)
            if uia_tree_has_visible_text(root, components.generated_share_title, max_depth=8):
                share_root = root
            else:
                click_result = _click_generate_qr_button(root)
                generate_button_info = click_result["button"]
                generate_click_point = click_result["point"]
                generate_click_method = click_result["method"]
                print(
                    f"生成收款码第{attempt}次点击: "
                    f"方式={generate_click_method}, 坐标={generate_click_point}",
                    flush=True,
                )
                share_root = _wait_for_visible_text_reacquiring(
                    root=root,
                    text=components.generated_share_title,
                    timeout_seconds=share_page_timeout,
                    pid=pid,
                    window_title=window_title,
                )

            if share_root is not None:
                break

            retry_errors.append(
                f"第{attempt}次点击后未在{share_page_timeout}秒内进入"
                f"“{components.generated_share_title}”，"
                f"点击方式={generate_click_method}，坐标={generate_click_point}"
            )
        except Exception as exc:
            retry_errors.append(f"第{attempt}次生成收款码失败: {exc}")

        if attempt < retry_count:
            print(
                f"生成收款码第{attempt}次失败，准备重试: {retry_errors[-1]}",
                flush=True,
            )
            time.sleep(components.generate_qr_retry_wait_seconds)

    if share_root is None:
        last_error = retry_errors[-1] if retry_errors else "未知原因"
        raise TimeoutError(
            f"点击“{components.generate_qr_button_text}”后未进入"
            f"“{components.generated_share_title}”，已重试{retry_count}次。"
            f"最后错误: {last_error}"
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
        "retry_count": retry_count,
        "retry_errors": retry_errors,
        "button": generate_button_info,
        "generate_click_point": generate_click_point,
        "generate_click_method": generate_click_method,
        **capture_result,
    }


def return_to_wait_payment_page(
    root: Any,
    timeout_seconds: float = 8.0,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    order_no: str = "",
) -> Dict[str, Any]:
    """从生成分享图页面返回两次，等待回到主界面订单等待付款状态."""

    components = WECHAT_PAY_ORDER
    back_click_points = []
    for _ in range(components.return_back_click_count):
        root = _reacquire_pay_order_root(root, pid, window_title)
        point = _click_any_text_or_relative(
            root,
            texts=components.return_back_button_texts,
            x_ratio=components.return_back_button_x_ratio,
            y_ratio=components.return_back_button_y_ratio,
        )
        back_click_points.append({"x": point[0], "y": point[1]})
        time.sleep(components.return_back_after_click_wait_seconds)

    wait_root, loaded_status = wait_order_status_loaded(
        root=root,
        order_no=order_no,
        timeout_seconds=timeout_seconds,
        pid=pid,
        window_title=window_title,
    )

    return {
        "returned": True,
        "back_click_count": components.return_back_click_count,
        "back_click_points": back_click_points,
        "wait_text": loaded_status["status_text"],
        "loaded_status": loaded_status,
    }


def wait_paid_then_close_pay_order(
    root: Any,
    order_no: str = "",
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    timeout_seconds: Optional[float] = None,
    on_paid: Optional[Callable[[], None]] = None,
    timings_seconds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """刷新订单状态；支付成功或达到重进上限后关闭并删除收款单."""

    components = WECHAT_PAY_ORDER
    workflow_started_at = time.perf_counter()
    workflow_timings = timings_seconds if timings_seconds is not None else {}
    close_delete_window_rect: Optional[tuple[int, int, int, int]] = None

    def run_timed(name: str, action: Callable[[], Any]) -> Any:
        stage_started_at = time.perf_counter()
        try:
            return action()
        finally:
            _record_timing(workflow_timings, name, stage_started_at)

    def click_close_delete_action(
        action_root: Any,
        text: str,
        x_ratio: float,
        y_ratio: float,
    ) -> tuple[int, int]:
        if components.fast_close_delete_coordinate_mode:
            if close_delete_window_rect is None:
                prepare_close_delete_coordinates(action_root)
            if close_delete_window_rect is None:
                raise RuntimeError("未获取到关闭/删除操作所需的窗口矩形.")
            left, top, width, height = close_delete_window_rect
            return click_screen_point(
                left + int(width * x_ratio),
                top + int(height * y_ratio),
            )
        return _click_text_or_relative(
            action_root,
            text=text,
            x_ratio=x_ratio,
            y_ratio=y_ratio,
        )

    def prepare_close_delete_coordinates(action_root: Any) -> tuple[int, int, int, int]:
        nonlocal close_delete_window_rect
        element = getattr(action_root, "element_info", action_root)
        rectangle = _safe_get(lambda: element.rectangle)
        left = int(_safe_get(lambda: rectangle.left, 0) or 0)
        top = int(_safe_get(lambda: rectangle.top, 0) or 0)
        right = int(_safe_get(lambda: rectangle.right, 0) or 0)
        bottom = int(_safe_get(lambda: rectangle.bottom, 0) or 0)
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width <= 0 or height <= 0:
            raise RuntimeError("关闭/删除操作的窗口矩形无效.")
        close_delete_window_rect = (left, top, width, height)
        return close_delete_window_rect

    def wait_close_delete_transition(action_root: Any, final: bool = False) -> Any:
        wait_seconds = (
            components.fast_delete_complete_wait_seconds
            if final
            else components.fast_close_delete_step_wait_seconds
        )
        time.sleep(max(0.0, wait_seconds))
        return action_root

    timeout = timeout_seconds
    deadline = None if timeout is None else time.time() + timeout
    refresh_count = 0
    last_refresh_result: Optional[Dict[str, Any]] = None
    order_card_point: Optional[tuple[int, int]] = None
    last_status: Optional[Dict[str, Any]] = None
    status_load_retry_count = 0
    payment_failed = False
    failure_reason: Optional[str] = None

    def refresh_limit_reached() -> bool:
        refresh_limit = max(0, int(components.max_payment_refresh_count))
        return refresh_limit > 0 and refresh_count >= refresh_limit

    def mark_payment_failed(status: Optional[Dict[str, Any]]) -> None:
        nonlocal payment_failed, failure_reason, order_card_point
        payment_failed = True
        failure_reason = (
            f"等待付款失败，已重新进入小程序{refresh_count}次，"
            f"订单状态仍为“{components.wait_payment_status_text}”。"
        )
        if status is not None:
            order_card_point = status.get("click_point")

    try:
        wait_payment_started_at = time.perf_counter()
        try:
            while True:
                try:
                    root = _reacquire_pay_order_root(root, pid, window_title)
                except PayOrderWindowUnavailableError as exc:
                    if deadline is not None and time.time() >= deadline:
                        raise TimeoutError(
                            f"等待付款超时，{timeout}秒内未看到“{components.paid_status_text}”；"
                            f"最近窗口状态: {exc}"
                        ) from exc
                    status_load_retry_count += 1
                    last_refresh_result = {
                        "loaded": False,
                        "retry_count": status_load_retry_count,
                        "error": str(exc),
                    }
                    print(
                        f"第{status_load_retry_count}次获取微信收款单窗口失败，"
                        f"将继续等待并重试: {exc}",
                        flush=True,
                    )
                    time.sleep(components.status_refresh_retry_wait_seconds)
                    continue
                last_status = _read_order_payment_status(root, str(order_no))
                if last_status["status"] == "paid":
                    order_card_point = last_status.get("click_point")
                    break
                if last_status["status"] not in {"unpaid", "unknown"}:
                    raise RuntimeError(f"无法识别订单状态: {last_status}")
                if deadline is not None and time.time() >= deadline:
                    raise TimeoutError(
                        f"等待付款超时，{timeout}秒内未看到“{components.paid_status_text}”."
                    )
                if (
                    last_status["status"] == "unpaid"
                    and refresh_limit_reached()
                ):
                    mark_payment_failed(last_status)
                    break
                refresh_started_at = time.time()
                try:
                    root, last_refresh_result = refresh_wait_payment_page(
                        root=root,
                        order_no=order_no,
                        pid=pid,
                        window_title=window_title,
                    )
                    refresh_count += 1
                except (TimeoutError, PayOrderWindowUnavailableError) as exc:
                    refresh_count += 1
                    status_load_retry_count += 1
                    last_refresh_result = {
                        "loaded": False,
                        "retry_count": status_load_retry_count,
                        "error": str(exc),
                    }
                    print(
                        f"第{status_load_retry_count}次重新进入小程序后未读取到订单状态，"
                        f"将再次重新进入: {exc}",
                        flush=True,
                    )
                    if refresh_limit_reached():
                        print(
                            f"已重新进入小程序{refresh_count}次，但当前订单状态仍未知；"
                            f"为避免误删已支付订单，将继续刷新直到读取到明确状态。",
                            flush=True,
                        )
                    time.sleep(components.status_refresh_retry_wait_seconds)
                    continue
                loaded_status = last_refresh_result.get("loaded_status") or {}
                last_status = loaded_status
                if loaded_status.get("status") == "paid":
                    order_card_point = loaded_status.get("click_point")
                    break
                if (
                    loaded_status.get("status") == "unpaid"
                    and refresh_limit_reached()
                ):
                    mark_payment_failed(loaded_status)
                    break
                refresh_elapsed = time.time() - refresh_started_at
                time.sleep(
                    max(0.0, components.payment_refresh_interval_seconds - refresh_elapsed)
                )
        finally:
            _record_timing(workflow_timings, "wait_payment", wait_payment_started_at)

        if not payment_failed and on_paid is not None:
            run_timed("notify_paid", on_paid)

        order_status_text = (
            components.wait_payment_status_text
            if payment_failed
            else components.paid_status_text
        )
        click_order_timing_name = (
            "click_unpaid_order" if payment_failed else "click_paid_order"
        )
        if payment_failed:
            root = run_timed(
                "reacquire_order_before_close",
                lambda: _reacquire_pay_order_root(None, pid, window_title),
            )
        before_detail_probe = _capture_payment_detail_visual_probe(root)
        if order_card_point is not None:
            detected_order_point = order_card_point
            order_card_point = run_timed(
                click_order_timing_name,
                lambda: click_screen_point(*detected_order_point),
            )
        else:
            order_card_point = run_timed(
                click_order_timing_name,
                lambda: _click_text_or_relative(
                    root,
                    text=order_status_text,
                    x_ratio=components.paid_card_x_ratio,
                    y_ratio=components.paid_card_y_ratio,
                ),
            )

        detail_result = run_timed(
            "wait_payment_detail",
            lambda: _wait_for_payment_detail_after_order_click(
                root=root,
                first_click_point=order_card_point,
                before_probe=before_detail_probe,
                pid=pid,
                window_title=window_title,
            ),
        )
        detail_root = detail_result["root"]
        if detail_root is None:
            raise TimeoutError(
                f"点击订单卡片{len(detail_result['attempts'])}次后仍未进入"
                f"“{components.payment_detail_title}”; "
                f"检测结果: {detail_result['attempts']}."
            )
        order_card_point = detail_result["click_point"]
        root = detail_root
        if components.fast_close_delete_coordinate_mode:
            run_timed(
                "prepare_close_delete_coordinates",
                lambda: prepare_close_delete_coordinates(root),
            )

        more_action_point = run_timed(
            "click_more_action_before_close",
            lambda: click_close_delete_action(
                root,
                components.more_action_text,
                components.more_action_x_ratio,
                components.more_action_y_ratio,
            ),
        )
        close_menu_root = run_timed(
            "wait_close_menu",
            lambda: (
                wait_close_delete_transition(root)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_visible_text_reacquiring(
                    root=root,
                    text=components.close_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                )
            ),
        )
        if close_menu_root is None:
            raise TimeoutError(f"点击更多操作后未看到“{components.close_pay_order_text}”.")
        root = close_menu_root

        close_point = run_timed(
            "click_close_order",
            lambda: click_close_delete_action(
                root,
                components.close_pay_order_text,
                components.close_pay_order_x_ratio,
                components.close_pay_order_y_ratio,
            ),
        )
        confirm_close_root = run_timed(
            "wait_confirm_close",
            lambda: (
                wait_close_delete_transition(root)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_visible_text_reacquiring(
                    root=root,
                    text=components.confirm_close_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                )
            ),
        )
        if confirm_close_root is None:
            raise TimeoutError(f"点击关闭收款单后未看到“{components.confirm_close_pay_order_text}”.")
        root = confirm_close_root
        confirm_close_uses_exact_title = (
            not components.fast_close_delete_coordinate_mode
            and uia_tree_has_visible_text(
                root,
                components.confirm_close_pay_order_text,
                max_depth=8,
                exact_title_only=True,
            )
        )

        confirm_close_point = run_timed(
            "click_confirm_close",
            lambda: click_close_delete_action(
                root,
                components.confirm_close_pay_order_text,
                components.confirm_close_pay_order_x_ratio,
                components.confirm_close_pay_order_y_ratio,
            ),
        )
        closed_root = run_timed(
            "wait_close_complete",
            lambda: (
                wait_close_delete_transition(root)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_text_to_disappear_reacquiring(
                    root=root,
                    text=components.confirm_close_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                    exact_title_only=confirm_close_uses_exact_title,
                )
            ),
        )
        if closed_root is None:
            raise TimeoutError(f"点击“{components.confirm_close_pay_order_text}”后弹窗未关闭.")
        root = closed_root

        more_action_after_close_point = run_timed(
            "click_more_action_before_delete",
            lambda: click_close_delete_action(
                root,
                components.more_action_text,
                components.more_action_x_ratio,
                components.more_action_y_ratio,
            ),
        )
        delete_menu_root = run_timed(
            "wait_delete_menu",
            lambda: (
                wait_close_delete_transition(root)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_visible_text_reacquiring(
                    root=root,
                    text=components.delete_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                )
            ),
        )
        if delete_menu_root is None:
            raise TimeoutError(
                f"确认关闭后再次点击更多操作，未看到“{components.delete_pay_order_text}”."
            )
        root = delete_menu_root

        delete_point = run_timed(
            "click_delete_order",
            lambda: click_close_delete_action(
                root,
                components.delete_pay_order_text,
                components.delete_pay_order_x_ratio,
                components.delete_pay_order_y_ratio,
            ),
        )
        confirm_delete_root = run_timed(
            "wait_confirm_delete",
            lambda: (
                wait_close_delete_transition(root)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_visible_text_reacquiring(
                    root=root,
                    text=components.confirm_delete_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                )
            ),
        )
        if confirm_delete_root is None:
            raise TimeoutError(
                f"点击删除收款单后未看到“{components.confirm_delete_pay_order_text}”."
            )
        root = confirm_delete_root
        confirm_delete_uses_exact_title = (
            not components.fast_close_delete_coordinate_mode
            and uia_tree_has_visible_text(
                root,
                components.confirm_delete_pay_order_text,
                max_depth=8,
                exact_title_only=True,
            )
        )

        confirm_delete_point = run_timed(
            "click_confirm_delete",
            lambda: click_close_delete_action(
                root,
                components.confirm_delete_pay_order_text,
                components.confirm_delete_pay_order_x_ratio,
                components.confirm_delete_pay_order_y_ratio,
            ),
        )
        deleted_root = run_timed(
            "wait_delete_complete",
            lambda: (
                wait_close_delete_transition(root, final=True)
                if components.fast_close_delete_coordinate_mode
                else _wait_for_text_to_disappear_reacquiring(
                    root=root,
                    text=components.confirm_delete_pay_order_text,
                    timeout_seconds=8.0,
                    pid=pid,
                    window_title=window_title,
                    exact_title_only=confirm_delete_uses_exact_title,
                )
            ),
        )
        if deleted_root is None:
            raise TimeoutError(f"点击“{components.confirm_delete_pay_order_text}”后弹窗未关闭.")

        return {
            "paid": not payment_failed,
            "payment_failed": payment_failed,
            "failure_reason": failure_reason,
            "closed": True,
            "deleted": True,
            "refresh_count": refresh_count,
            "status_load_retry_count": status_load_retry_count,
            "last_refresh": last_refresh_result,
            "last_status": last_status,
            "payment_detail_detection": detail_result["detection"],
            "order_card_click_attempts": detail_result["attempts"],
            "timings_seconds": workflow_timings,
            "order_card_click_point": {
                "x": order_card_point[0],
                "y": order_card_point[1],
            },
            "paid_card_click_point": (
                {"x": order_card_point[0], "y": order_card_point[1]}
                if not payment_failed
                else None
            ),
            "more_action_click_point": {
                "x": more_action_point[0],
                "y": more_action_point[1],
            },
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
    finally:
        _record_timing(
            workflow_timings,
            "wait_paid_then_close_total",
            workflow_started_at,
        )


def refresh_wait_payment_page(
    root: Any,
    order_no: str = "",
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> tuple[Any, Dict[str, Any]]:
    """通过小程序右上角菜单点击“重新进入小程序”刷新主界面."""

    components = WECHAT_PAY_ORDER
    root = _reacquire_pay_order_root(root, pid, window_title)
    menu_point = _click_any_text_or_relative(
        root,
        texts=components.mini_program_menu_texts,
        x_ratio=components.mini_program_menu_x_ratio,
        y_ratio=components.mini_program_menu_y_ratio,
    )
    time.sleep(components.refresh_menu_after_click_wait_seconds)

    reenter_point = _click_text_or_relative(
        root,
        text=components.reenter_mini_program_text,
        x_ratio=components.reenter_mini_program_x_ratio,
        y_ratio=components.reenter_mini_program_y_ratio,
    )
    time.sleep(components.refresh_reenter_after_click_wait_seconds)
    refreshed_root, loaded_status = wait_order_status_loaded(
        root=None,
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
    last_status: Optional[Dict[str, Any]] = None
    last_reacquire_error = ""
    while time.time() < deadline:
        try:
            root = _reacquire_pay_order_root(root, pid, window_title)
        except PayOrderWindowUnavailableError as exc:
            last_reacquire_error = str(exc)
            time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
            continue
        last_status = _read_order_payment_status(root, order_no)
        if last_status["status"] in {"unpaid", "paid"}:
            return root, last_status
        time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
    debug = (last_status or {}).get("debug") or {}
    raise TimeoutError(
        f"重新进入小程序后未在{timeout_seconds}秒内读取到订单状态"
        f"（{WECHAT_PAY_ORDER.wait_payment_status_text}/{WECHAT_PAY_ORDER.paid_status_text}）; "
        f"识别结果: {debug}; 最近窗口状态: {last_reacquire_error or '正常'}."
    )


def _wait_for_visible_text_reacquiring(
    root: Any,
    text: str,
    timeout_seconds: float,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> Optional[Any]:
    deadline = time.time() + timeout_seconds
    current_root = root
    next_reacquire_at = (
        time.time() + WECHAT_PAY_ORDER.window_reacquire_interval_seconds
        if _control_has_valid_rectangle(current_root)
        else 0.0
    )
    while time.time() < deadline:
        if _control_has_valid_rectangle(current_root) and uia_tree_has_visible_text(
            current_root,
            text,
            max_depth=8,
        ):
            return current_root
        now = time.time()
        if now >= next_reacquire_at:
            try:
                current_root = _reacquire_pay_order_root(None, pid, window_title)
            except PayOrderWindowUnavailableError:
                time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
                continue
            next_reacquire_at = now + WECHAT_PAY_ORDER.window_reacquire_interval_seconds
        time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
    return None


def _capture_payment_detail_visual_probe(root: Any) -> Optional[Dict[str, Any]]:
    components = WECHAT_PAY_ORDER
    try:
        return capture_control_visual_probe(
            root,
            sample_width=components.payment_detail_visual_sample_width,
            sample_height=components.payment_detail_visual_sample_height,
        )
    except Exception:
        return None


def _wait_for_payment_detail_after_order_click(
    root: Any,
    first_click_point: tuple[int, int],
    before_probe: Optional[Dict[str, Any]],
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> Dict[str, Any]:
    """点击订单卡片主体并通过 UIA 文本或画面变化确认进入详情页."""

    components = WECHAT_PAY_ORDER
    candidates = _build_order_card_click_candidates(root, first_click_point)
    attempts: list[Dict[str, Any]] = []
    current_probe = before_probe
    last_point = first_click_point

    for index, point in enumerate(candidates):
        if index > 0:
            current_probe = _capture_payment_detail_visual_probe(root)
            click_screen_point(*point)
        last_point = point
        time.sleep(components.payment_detail_click_wait_seconds)

        after_probe = _capture_payment_detail_visual_probe(root)
        visual_change_ratio: Optional[float] = None
        if current_probe is not None and after_probe is not None:
            try:
                visual_change_ratio = compare_control_visual_probes(
                    current_probe,
                    after_probe,
                    pixel_difference_threshold=(
                        components.payment_detail_visual_pixel_threshold
                    ),
                )
            except (TypeError, ValueError):
                visual_change_ratio = None

        visual_changed = (
            visual_change_ratio is not None
            and visual_change_ratio >= components.payment_detail_visual_change_ratio
        )
        title_found = False
        if not visual_changed:
            try:
                title_found = uia_tree_has_visible_text(
                    root,
                    components.payment_detail_title,
                    max_depth=8,
                )
            except Exception:
                title_found = False
        attempts.append(
            {
                "attempt": index + 1,
                "click_point": {"x": point[0], "y": point[1]},
                "title_found": title_found,
                "visual_change_ratio": visual_change_ratio,
                "visual_changed": visual_changed,
            }
        )
        if title_found or visual_changed:
            return {
                "root": root,
                "click_point": point,
                "detection": "uia_title" if title_found else "visual_change",
                "attempts": attempts,
            }

    detail_root = _wait_for_visible_text_reacquiring(
        root=root,
        text=components.payment_detail_title,
        timeout_seconds=components.payment_detail_final_wait_seconds,
        pid=pid,
        window_title=window_title,
    )
    return {
        "root": detail_root,
        "click_point": last_point,
        "detection": "uia_title_delayed" if detail_root is not None else "not_detected",
        "attempts": attempts,
    }


def _build_order_card_click_candidates(
    root: Any,
    first_click_point: tuple[int, int],
) -> list[tuple[int, int]]:
    """围绕已定位的目标订单生成卡片主体点击候选点，不跨到其他订单."""

    root_info = uia_control_search_info(root)
    rectangle = root_info.get("rectangle") or {}
    left = int(rectangle.get("left") or 0)
    top = int(rectangle.get("top") or 0)
    width = int(rectangle.get("width") or 0)
    height = int(rectangle.get("height") or 0)
    if width <= 0 or height <= 0:
        return [first_click_point]

    right = left + width - 1
    bottom = top + height - 1
    candidates: list[tuple[int, int]] = []
    for x_offset_ratio, y_offset_ratio in WECHAT_PAY_ORDER.order_card_click_retry_offsets:
        point = (
            min(right, max(left, first_click_point[0] + int(width * x_offset_ratio))),
            min(bottom, max(top, first_click_point[1] + int(height * y_offset_ratio))),
        )
        if point not in candidates:
            candidates.append(point)
    return candidates or [first_click_point]


def _wait_for_text_to_disappear_reacquiring(
    root: Any,
    text: str,
    timeout_seconds: float,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
    exact_title_only: bool = False,
) -> Optional[Any]:
    deadline = time.time() + timeout_seconds
    current_root = root
    next_reacquire_at = (
        time.time() + WECHAT_PAY_ORDER.window_reacquire_interval_seconds
        if _control_has_valid_rectangle(current_root)
        else 0.0
    )
    while time.time() < deadline:
        if _control_has_valid_rectangle(current_root) and not uia_tree_has_visible_text(
            current_root,
            text,
            max_depth=8,
            exact_title_only=exact_title_only,
        ):
            return current_root
        now = time.time()
        if now >= next_reacquire_at:
            try:
                current_root = _reacquire_pay_order_root(None, pid, window_title)
            except PayOrderWindowUnavailableError:
                time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
                continue
            next_reacquire_at = now + WECHAT_PAY_ORDER.window_reacquire_interval_seconds
        time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)
    return None


def _reacquire_pay_order_root(
    current_root: Any,
    pid: Optional[int] = DEFAULT_PID,
    window_title: str = DEFAULT_WINDOW_TITLE,
) -> Any:
    from pywinauto import Desktop  # type: ignore

    enable_fast_timings()
    if _control_has_valid_rectangle(current_root):
        return current_root

    desktop = Desktop(backend="uia")
    deadline = time.time() + WECHAT_PAY_ORDER.window_reacquire_timeout_seconds
    last_error: Optional[Exception] = None
    while True:
        try:
            return find_first_uia_top_window(desktop, pid, window_title)
        except Exception as exc:
            last_error = exc
        if pid is not None:
            try:
                return find_first_uia_top_window(desktop, None, window_title)
            except Exception as exc:
                last_error = exc
        if _control_has_valid_rectangle(current_root):
            return current_root
        if time.time() >= deadline:
            raise PayOrderWindowUnavailableError(
                f"{WECHAT_PAY_ORDER.window_reacquire_timeout_seconds}秒内未重新获取"
                f"标题包含“{window_title}”的窗口"
            ) from last_error
        time.sleep(WECHAT_PAY_ORDER.wait_poll_interval_seconds)


def _control_has_valid_rectangle(control: Any) -> bool:
    if control is None:
        return False
    try:
        element = getattr(control, "element_info", control)
        rectangle = _safe_get(lambda: element.rectangle)
        left = int(_safe_get(lambda: rectangle.left, 0) or 0)
        top = int(_safe_get(lambda: rectangle.top, 0) or 0)
        right = int(_safe_get(lambda: rectangle.right, 0) or 0)
        bottom = int(_safe_get(lambda: rectangle.bottom, 0) or 0)
        return right > left and bottom > top
    except Exception:
        return False


def _collect_visible_uia_snapshot(root: Any) -> list[Dict[str, Any]]:
    """一次遍历收集状态识别所需的可见文本和矩形，供多个匹配步骤复用."""

    snapshot: list[Dict[str, Any]] = []
    for item, depth in iter_uia_tree(root, max_depth=10):
        info = uia_control_search_info(item)
        rectangle = info.get("rectangle") or {}
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        if info.get("visible") is False or width <= 0 or height <= 0:
            continue
        snapshot.append(
            {
                "depth": depth,
                "control_type": str(info.get("control_type") or ""),
                "text_blob": str(info.get("text_blob") or ""),
                "rectangle": {
                    "left": int(rectangle.get("left") or 0),
                    "top": int(rectangle.get("top") or 0),
                    "right": int(rectangle.get("right") or 0),
                    "bottom": int(rectangle.get("bottom") or 0),
                    "width": width,
                    "height": height,
                },
            }
        )
    return snapshot


def _read_order_payment_status(root: Any, order_no: str) -> Dict[str, Any]:
    components = WECHAT_PAY_ORDER
    snapshot = _collect_visible_uia_snapshot(root)
    paid_point = _find_order_status_card_click_point(
        root,
        order_no,
        components.paid_status_text,
        snapshot=snapshot,
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
        snapshot=snapshot,
    )
    if unpaid_point is not None:
        return {
            "status": "unpaid",
            "status_text": components.wait_payment_status_text,
            "click_point": unpaid_point,
        }

    page_text = _collect_visible_uia_text(root, snapshot=snapshot)
    paid_text_found = components.paid_status_text in page_text
    unpaid_text_found = components.wait_payment_status_text in page_text
    if paid_text_found and not unpaid_text_found:
        paid_status_rects = _find_visible_text_rects(
            root,
            components.paid_status_text,
            snapshot=snapshot,
        )
        return {
            "status": "paid",
            "status_text": components.paid_status_text,
            "click_point": (
                _point_above_rect(paid_status_rects[0], 45)
                if paid_status_rects
                else None
            ),
            "source": "page_single_status",
        }
    if unpaid_text_found and not paid_text_found:
        return {
            "status": "unpaid",
            "status_text": components.wait_payment_status_text,
            "click_point": None,
            "source": "page_single_status",
        }
    if page_text.strip() and not unpaid_text_found:
        return {
            "status": "paid",
            "status_text": components.paid_status_text,
            "click_point": _relative_screen_point(
                root,
                components.paid_card_x_ratio,
                components.paid_card_y_ratio,
            ),
            "source": "page_text_without_unpaid",
        }
    return {
        "status": "unknown",
        "status_text": "",
        "click_point": None,
        "debug": {
            "order_text_found": bool(order_no and order_no in page_text),
            "paid_text_found": paid_text_found,
            "unpaid_text_found": unpaid_text_found,
        },
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
    snapshot: Optional[list[Dict[str, Any]]] = None,
) -> Optional[tuple[int, int]]:
    current_snapshot = snapshot if snapshot is not None else _collect_visible_uia_snapshot(root)
    status_rects = _find_visible_text_rects(
        root,
        status_text,
        snapshot=current_snapshot,
    )
    if not order_no:
        return _point_above_rect(status_rects[0], 45) if status_rects else None

    order_rects = _find_visible_text_rects(
        root,
        order_no,
        snapshot=current_snapshot,
    )
    matched_order_rects = [
        order_rect
        for order_rect in order_rects
        if any(
            _looks_like_same_order_card(order_rect, status_rect)
            for status_rect in status_rects
        )
    ]
    if matched_order_rects:
        matched_order_rects.sort(
            key=lambda rectangle: rectangle["width"] * rectangle["height"]
        )
        return _rect_center(matched_order_rects[0])

    container_rect = _find_smallest_control_containing_texts(
        root,
        (order_no, status_text),
        snapshot=current_snapshot,
    )
    if container_rect is not None and not _rectangle_covers_root(root, container_rect):
        return _rect_center(container_rect)

    page_text = _collect_visible_uia_text(root, snapshot=current_snapshot)
    if order_no not in page_text or status_text not in page_text:
        return None

    opposite_status = (
        WECHAT_PAY_ORDER.wait_payment_status_text
        if status_text == WECHAT_PAY_ORDER.paid_status_text
        else WECHAT_PAY_ORDER.paid_status_text
    )
    if opposite_status in page_text:
        return None
    if order_rects:
        return _rect_center(order_rects[0])
    if status_rects:
        return _point_above_rect(status_rects[0], 45)
    return _relative_screen_point(
        root,
        WECHAT_PAY_ORDER.paid_card_x_ratio,
        WECHAT_PAY_ORDER.paid_card_y_ratio,
    )


def _find_smallest_control_containing_texts(
    root: Any,
    texts: tuple[str, ...],
    snapshot: Optional[list[Dict[str, Any]]] = None,
) -> Optional[Dict[str, int]]:
    candidates: list[tuple[int, int, Dict[str, int]]] = []
    current_snapshot = snapshot if snapshot is not None else _collect_visible_uia_snapshot(root)
    for item in current_snapshot:
        depth = int(item.get("depth") or 0)
        rectangle = item.get("rectangle") or {}
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        blob = str(item.get("text_blob") or "")
        if not all(text in blob for text in texts):
            continue
        rect = {
            "left": int(rectangle.get("left") or 0),
            "top": int(rectangle.get("top") or 0),
            "right": int(rectangle.get("right") or 0),
            "bottom": int(rectangle.get("bottom") or 0),
            "width": width,
            "height": height,
        }
        candidates.append((width * height, -depth, rect))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _collect_visible_uia_text(
    root: Any,
    snapshot: Optional[list[Dict[str, Any]]] = None,
) -> str:
    current_snapshot = snapshot if snapshot is not None else _collect_visible_uia_snapshot(root)
    parts = [
        str(item.get("text_blob") or "").strip()
        for item in current_snapshot
        if str(item.get("text_blob") or "").strip()
    ]
    return "\n".join(parts)


def _rectangle_covers_root(root: Any, rectangle: Dict[str, int]) -> bool:
    root_info = uia_control_search_info(root)
    root_rectangle = root_info.get("rectangle") or {}
    root_area = int(root_rectangle.get("width") or 0) * int(root_rectangle.get("height") or 0)
    rectangle_area = rectangle["width"] * rectangle["height"]
    return root_area > 0 and rectangle_area >= root_area * 0.80


def _relative_screen_point(root: Any, x_ratio: float, y_ratio: float) -> tuple[int, int]:
    root_info = uia_control_search_info(root)
    rectangle = root_info.get("rectangle") or {}
    left = int(rectangle.get("left") or 0)
    top = int(rectangle.get("top") or 0)
    width = int(rectangle.get("width") or 0)
    height = int(rectangle.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("目标窗口矩形无效，无法计算订单卡片点击位置.")
    return left + int(width * x_ratio), top + int(height * y_ratio)


def _find_visible_text_rects(
    root: Any,
    text: str,
    snapshot: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, int]]:
    rects: list[Dict[str, int]] = []
    current_snapshot = snapshot if snapshot is not None else _collect_visible_uia_snapshot(root)
    for item in current_snapshot:
        if int(item.get("depth") or 0) > 8:
            continue
        if item.get("control_type") == "Document":
            continue
        if text not in str(item.get("text_blob") or ""):
            continue
        rectangle = item.get("rectangle") or {}
        rects.append(
            {
                key: int(rectangle.get(key) or 0)
                for key in ("left", "top", "right", "bottom", "width", "height")
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


def _point_above_rect(rectangle: Dict[str, int], offset_pixels: int) -> tuple[int, int]:
    center_x, center_y = _rect_center(rectangle)
    return center_x, center_y - max(0, offset_pixels)


def _click_generate_qr_button(root: Any) -> Dict[str, Any]:
    components = WECHAT_PAY_ORDER
    target = find_uia_click_target(
        root,
        text=components.generate_qr_button_text,
        max_depth=10,
    )
    if target is not None:
        point, button_info, method = _click_uia_control_center(
            target,
            physical_click=True,
        )
    else:
        point = click_relative(
            root,
            components.generate_qr_button_x_ratio,
            components.generate_qr_button_y_ratio,
        )
        button_info = None
        method = "relative_fallback"
    return {
        "button": button_info,
        "point": {"x": point[0], "y": point[1]},
        "method": method,
    }


def _click_labeled_input_or_relative(
    root: Any,
    label_text: str,
    x_ratio: float,
    y_ratio: float,
) -> tuple[int, int]:
    edit_control = _find_edit_control_near_text(root, label_text)
    if edit_control is not None:
        try:
            point, _info, _method = _click_uia_control_center(edit_control)
            return point
        except Exception:
            pass

    target = find_uia_click_target(root, text=label_text, max_depth=10)
    if target is not None:
        target_info = _uia_control_to_info(target, 0, 0, "input-label")
        control_type = str(target_info.get("control_type") or "")
        if control_type not in {"Text", "Document"}:
            try:
                point, _info, _method = _click_uia_control_center(target)
                return point
            except Exception:
                pass

    return click_relative(root, x_ratio, y_ratio)


def _find_edit_control_near_text(root: Any, label_text: str) -> Optional[Any]:
    label_rects = _find_visible_text_rects(root, label_text) if label_text else []
    candidates: list[tuple[tuple[int, int, int], Any]] = []

    for item, depth in iter_uia_tree(root, max_depth=10):
        info = uia_control_search_info(item)
        rectangle = info.get("rectangle") or {}
        width = int(rectangle.get("width") or 0)
        height = int(rectangle.get("height") or 0)
        control_type = str(info.get("control_type") or "")
        if control_type not in {"Edit", "ComboBox"}:
            continue
        if info.get("visible") is False or info.get("enabled") is False:
            continue
        if width <= 0 or height <= 0:
            continue

        score = (10000, width * height, depth)
        if label_rects:
            matched_label = False
            edit_rect = {
                "left": int(rectangle.get("left") or 0),
                "top": int(rectangle.get("top") or 0),
                "right": int(rectangle.get("right") or 0),
                "bottom": int(rectangle.get("bottom") or 0),
                "width": width,
                "height": height,
            }
            for label_rect in label_rects:
                vertical_distance = abs(_rect_center(edit_rect)[1] - _rect_center(label_rect)[1])
                horizontal_distance = edit_rect["left"] - label_rect["left"]
                if vertical_distance > 90 or horizontal_distance < -80:
                    continue
                score = (
                    vertical_distance,
                    abs(horizontal_distance),
                    depth,
                )
                matched_label = True
                break
            if not matched_label:
                continue

        candidates.append((score, item))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _click_any_text_or_relative(
    root: Any,
    texts: tuple[str, ...],
    x_ratio: float,
    y_ratio: float,
) -> tuple[int, int]:
    for text in texts:
        if not text:
            continue
        target = find_uia_click_target(root, text=text, max_depth=10)
        if target is None:
            continue
        try:
            point, _info, _method = _click_uia_control_center(target)
            return point
        except Exception:
            continue

    return click_relative(root, x_ratio, y_ratio)


def _click_text_or_relative(
    root: Any,
    text: str,
    x_ratio: float,
    y_ratio: float,
) -> tuple[int, int]:
    point, _target_info, _method = _click_text_or_relative_with_info(
        root=root,
        text=text,
        x_ratio=x_ratio,
        y_ratio=y_ratio,
    )
    return point


def _click_text_or_relative_with_info(
    root: Any,
    text: str,
    x_ratio: float,
    y_ratio: float,
) -> tuple[tuple[int, int], Optional[Dict[str, Any]], str]:
    target = find_uia_click_target(root, text=text, max_depth=10)
    if target is not None:
        try:
            return _click_uia_control_center(target)
        except Exception:
            pass

    point = click_relative(root, x_ratio, y_ratio)
    return point, None, "relative"


def _click_uia_control_center(
    control: Any,
    physical_click: bool = False,
) -> tuple[tuple[int, int], Dict[str, Any], str]:
    target_info = uia_control_search_info(control)
    rectangle = target_info.get("rectangle") or {}
    left = int(rectangle.get("left") or 0)
    top = int(rectangle.get("top") or 0)
    width = int(rectangle.get("width") or 0)
    height = int(rectangle.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("目标控件矩形无效，无法点击.")

    point = (left + width // 2, top + height // 2)
    if physical_click:
        click_screen_point(*point)
        method = "uia_element_center_click"
    else:
        method = invoke_or_click(control)
    return point, target_info, method


def _fill_amount_by_keypad(root: Any, amount: str) -> tuple[int, int]:
    components = WECHAT_PAY_ORDER
    _validate_amount_text(amount)

    if components.fast_input_coordinate_mode:
        amount_point = click_relative(
            root,
            components.amount_input_x_ratio,
            components.amount_input_y_ratio,
        )
    else:
        amount_point = _click_labeled_input_or_relative(
            root,
            components.amount_input_text,
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
        invoke_or_click(button)
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
