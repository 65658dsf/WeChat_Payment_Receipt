# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from utools.components.wechat_pay_order import (
    DEFAULT_WINDOW_TITLE,
)
from utools.io.json_output import output_json_result
from utools.ui.inspector import (
    find_windows_by_title,
    get_process_component_info,
)
from utools.wechat.pay_order import generate_pay_order


# ===== 在这里配置运行参数 =====
# PID为None时，自动在系统窗口中查找标题包含WINDOW_TITLE的进程。
PID: Optional[int] = None
WINDOW_TITLE = DEFAULT_WINDOW_TITLE

# backend可选: "auto", "uia", "win32"。建议保持auto。
BACKEND = "auto"

# None表示采集整棵组件树；调试时可设为0、1、2限制深度。
MAX_DEPTH: Optional[int] = None

# True包含隐藏/离屏控件；False只保留可见控件。
INCLUDE_HIDDEN = True

# True只查找窗口/PID，不采集组件树。
FIND_ONLY = False

# True时自动点击“发起收款”，进入“创建收款单”界面，填写金额和订单号后再采集组件信息。
Generator_PayOrder = True
Generator_PayOrder_Amount = "1.00"
Generator_PayOrder_OrderNo = "ORDER001"

# 需要写入文件时填写路径；None表示不写文件。
OUTPUT: Optional[str] = r"outputs\output.json"


def run() -> Dict[str, Any]:
    if FIND_ONLY:
        return {
            "query": {"window_title": WINDOW_TITLE},
            "windows": find_windows_by_title(WINDOW_TITLE),
        }

    action_result: Optional[Dict[str, Any]] = None
    collect_pid = PID
    collect_hwnd: Optional[int] = None

    if Generator_PayOrder:
        action_result = generate_pay_order(
            amount=Generator_PayOrder_Amount,
            order_no=Generator_PayOrder_OrderNo,
            pid=PID,
            window_title=WINDOW_TITLE,
        )
        action_pid = action_result.get("pid")
        if isinstance(action_pid, int):
            collect_pid = action_pid
        else:
            collect_pid = PID

        action_window = action_result.get("window") or {}
        action_hwnd = action_window.get("hwnd")
        if isinstance(action_hwnd, int):
            collect_hwnd = action_hwnd

    result = get_process_component_info(
        pid=collect_pid,
        window_title=WINDOW_TITLE,
        backend=BACKEND,
        max_depth=MAX_DEPTH,
        include_hidden=INCLUDE_HIDDEN,
        hwnd=collect_hwnd,
    )

    if action_result is not None:
        result["actions"] = {"Generator_PayOrder": action_result}

    return result


if __name__ == "__main__":
    run()
