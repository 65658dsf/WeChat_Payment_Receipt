# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WechatPayOrderComponents:
    window_title: str = "微信收款单"
    create_pay_order_title: str = "创建收款单"
    create_pay_order_button_text: str = "发起收款"
    amount_input_x_ratio: float = 0.20
    amount_input_y_ratio: float = 0.21
    description_input_x_ratio: float = 0.32
    description_input_y_ratio: float = 0.30
    amount_clear_backspace_count: int = 0
    wait_poll_interval_seconds: float = 0.05
    paste_select_wait_seconds: float = 0.01
    paste_after_wait_seconds: float = 0.02


DEFAULT_PID: Optional[int] = None
DEFAULT_WINDOW_TITLE = WechatPayOrderComponents().window_title
WECHAT_PAY_ORDER = WechatPayOrderComponents()
