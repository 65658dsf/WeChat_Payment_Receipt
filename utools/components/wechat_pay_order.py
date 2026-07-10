# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WechatPayOrderComponents:
    window_title: str = "微信收款单"
    create_pay_order_title: str = "创建收款单"
    create_pay_order_button_text: str = "发起收款"
    created_dialog_title: str = "已创建"
    amount_input_text: str = "金额"
    description_input_text: str = "收款说明"
    create_button_text: str = "创建"
    generate_qr_button_text: str = "生成收款码"
    generated_share_title: str = "生成分享图"
    wait_payment_status_text: str = "暂无人付款"
    paid_status_text: str = "已支付"
    payment_detail_title: str = "收款记录"
    more_action_text: str = "更多操作"
    close_pay_order_text: str = "关闭收款单"
    confirm_close_pay_order_text: str = "确定关闭"
    delete_pay_order_text: str = "删除收款单"
    confirm_delete_pay_order_text: str = "确定删除"
    reenter_mini_program_text: str = "重新进入小程序"
    return_back_button_texts: tuple[str, ...] = ("返回", "返回上一页")
    mini_program_menu_texts: tuple[str, ...] = ("更多", "更多功能", "菜单")
    amount_input_x_ratio: float = 0.20
    amount_input_y_ratio: float = 0.21
    description_input_x_ratio: float = 0.32
    description_input_y_ratio: float = 0.30
    create_button_x_ratio: float = 0.50
    create_button_y_ratio: float = 0.94
    generate_qr_button_x_ratio: float = 0.29
    generate_qr_button_y_ratio: float = 0.88
    return_back_button_x_ratio: float = 0.05
    return_back_button_y_ratio: float = 0.05
    return_back_click_count: int = 2
    paid_card_x_ratio: float = 0.28
    paid_card_y_ratio: float = 0.45
    more_action_x_ratio: float = 0.87
    more_action_y_ratio: float = 0.13
    close_pay_order_x_ratio: float = 0.50
    close_pay_order_y_ratio: float = 0.87
    confirm_close_pay_order_x_ratio: float = 0.66
    confirm_close_pay_order_y_ratio: float = 0.55
    delete_pay_order_x_ratio: float = 0.50
    delete_pay_order_y_ratio: float = 0.87
    confirm_delete_pay_order_x_ratio: float = 0.66
    confirm_delete_pay_order_y_ratio: float = 0.55
    mini_program_menu_x_ratio: float = 0.735
    mini_program_menu_y_ratio: float = 0.055
    reenter_mini_program_x_ratio: float = 0.57
    reenter_mini_program_y_ratio: float = 0.365
    qr_card_left_ratio: float = 0.165
    qr_card_top_ratio: float = 0.247
    qr_card_right_ratio: float = 0.843
    qr_card_bottom_ratio: float = 0.663
    amount_clear_backspace_count: int = 0
    fast_input_coordinate_mode: bool = True
    wait_poll_interval_seconds: float = 0.05
    window_reacquire_interval_seconds: float = 0.25
    window_reacquire_timeout_seconds: float = 3.0
    paste_select_wait_seconds: float = 0.01
    paste_after_wait_seconds: float = 0.02
    return_back_after_click_wait_seconds: float = 0.15
    payment_refresh_interval_seconds: float = 1.0
    refresh_menu_after_click_wait_seconds: float = 0.15
    refresh_reenter_after_click_wait_seconds: float = 0.70
    order_status_load_timeout_seconds: float = 8.0
    status_refresh_retry_wait_seconds: float = 0.30
    generate_qr_retry_count: int = 3
    generate_qr_page_timeout_seconds: float = 4.0
    generate_qr_retry_wait_seconds: float = 0.10


DEFAULT_PID: Optional[int] = None
DEFAULT_WINDOW_TITLE = WechatPayOrderComponents().window_title
WECHAT_PAY_ORDER = WechatPayOrderComponents()
