# Agent 组件索引

这个文件用于帮助后续 Agent 快速理解项目。新增、移动、删除函数时，请同步更新本文件。

## 主入口

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `run()` | `D:\LemonDev\收款单收款\main.py` | 按 `main.py` 顶部配置执行流程：可只查找窗口，也可自动进入创建收款单界面、填写金额/订单号后采集组件树。 |

## UI 获取模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `get_process_component_info()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 获取指定窗口/进程的组件树，优先走 UIA，失败时回退 Win32。支持按 PID、窗口标题、顶级窗口 hwnd 精确匹配。 |
| `find_windows_by_title()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 按顶级窗口标题查找窗口信息和 PID。 |
| `_collect_by_uia()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | UIA 后端采集入口，返回顶级窗口和组件列表。 |
| `_find_uia_top_windows()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 在 UIA 顶级窗口中按 PID、标题、hwnd 查找候选窗口，并按可用性排序。 |
| `_uia_window_sort_key()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 给 UIA 顶级窗口排序，优先可见、位置正常、面积大的窗口。 |
| `_walk_uia_tree()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 递归遍历 UIA 控件树并写入组件列表。 |
| `_uia_control_to_info()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 将 UIA 控件包装成 JSON 可序列化的组件信息。 |
| `_collect_by_win32()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | Win32 后端采集入口，用于 UIA 不可用时兜底。 |
| `_find_win32_top_windows()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 在 Win32 顶级窗口中按 PID、标题、hwnd 查找候选窗口。 |
| `_walk_win32_tree()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 递归遍历 Win32 子窗口。 |
| `_win32_hwnd_to_info()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 将 Win32 hwnd 包装成 JSON 可序列化的组件信息。 |
| `_empty_result()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 构建采集失败或空结果结构。 |
| `_safe_get()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 安全执行无参取值函数，异常时返回默认值。 |
| `_safe_method()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 安全调用对象方法，方法不存在或异常时返回默认值。 |
| `_rect_to_dict()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 将 UIA/Win32 矩形对象转换为字典。 |
| `_enum_windows()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | Win32 `EnumWindows` 封装。 |
| `_get_window_pid()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 获取 hwnd 对应进程 PID。 |
| `_get_window_text()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 获取 hwnd 窗口标题文本。 |
| `_get_class_name()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 获取 hwnd 窗口类名。 |
| `_get_window_rect()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 获取 hwnd 窗口坐标和尺寸。 |
| `_count_direct_win32_children()` | `D:\LemonDev\收款单收款\utools\ui\inspector.py` | 统计 hwnd 的直接子窗口数量。 |

## UI 操作模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `find_first_uia_top_window()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 找到首个可用 UIA 顶级窗口；遇到隐藏壳窗口时回退到同 PID 的可见窗口。 |
| `is_usable_top_window()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 判断顶级窗口是否可见、尺寸有效、位置正常。 |
| `iter_uia_tree()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 以栈方式遍历 UIA 控件树。 |
| `uia_text_blob()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 汇总控件的 name、window_text、value，作为查找文本。 |
| `find_uia_click_target()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 按文本查找最合适的可点击控件，优先 Button、精确文本、小面积控件。 |
| `enable_fast_timings()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 降低 pywinauto 默认动作等待时间，用于加快点击、聚焦、键盘输入。 |
| `click_relative()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 按控件矩形相对坐标点击，适合小程序内部不暴露标准控件的区域；金额数字键盘依赖它。 |
| `paste_text()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 用剪贴板向当前焦点控件粘贴文本，可选择先全选清空；订单号填写依赖它。 |
| `set_clipboard_text()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 使用 Windows Unicode 剪贴板 API 写入文本。 |
| `wait_for_visible_uia_text()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 在指定窗口内等待可见文本出现。 |
| `uia_tree_has_visible_text()` | `D:\LemonDev\收款单收款\utools\ui\operator.py` | 判断控件树中是否有可见、非 Document、尺寸有效的目标文本。 |

## 微信收款单业务模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `open_create_pay_order_page()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 自动找到“微信收款单”窗口，点击“发起收款”，等待进入“创建收款单”界面，并返回动作结果。 |
| `generate_pay_order()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 自动进入“创建收款单”界面，并把金额填到金额区域、订单号填到“收款说明”。 |
| `fill_create_pay_order_fields()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 在已打开的创建收款单界面内填写金额和订单号。 |
| `_fill_amount_by_keypad()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 点击金额区域后，通过小程序数字键盘坐标输入金额。 |
| `_validate_amount_text()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 校验金额只能包含数字和一个小数点，并且至少包含一个数字。 |
| `_open_create_pay_order_page()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 内部函数，返回创建收款单页面根控件和动作结果。 |
| `_require_non_empty()` | `D:\LemonDev\收款单收款\utools\wechat\pay_order.py` | 校验金额、订单号等必填参数不为空。 |

## 组件常量模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `WechatPayOrderComponents` | `D:\LemonDev\收款单收款\utools\components\wechat_pay_order.py` | 保存微信收款单窗口标题、创建页标题、发起收款按钮文案、金额/说明输入区域的窗口相对坐标，以及快速模式等待参数。 |
| `DEFAULT_PID` | `D:\LemonDev\收款单收款\utools\components\wechat_pay_order.py` | 默认 PID，当前为 `None`，表示自动查找。 |
| `DEFAULT_WINDOW_TITLE` | `D:\LemonDev\收款单收款\utools\components\wechat_pay_order.py` | 默认窗口标题，当前为“微信收款单”。 |
| `WECHAT_PAY_ORDER` | `D:\LemonDev\收款单收款\utools\components\wechat_pay_order.py` | 默认的 `WechatPayOrderComponents` 实例。 |

## IO 模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `output_json_result()` | `D:\LemonDev\收款单收款\utools\io\json_output.py` | 打印 JSON，并在指定路径写入输出文件；会自动创建输出目录。 |
