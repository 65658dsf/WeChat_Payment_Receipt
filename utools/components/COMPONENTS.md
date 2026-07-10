# Agent 组件索引

这个文件用于帮助后续 Agent 快速理解项目。新增、移动、删除函数时，请同步更新本文件。

## 主入口

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `run()` | `.\main.py` | 按 `main.py` 顶部配置执行流程：可只查找窗口，也可自动创建收款单、保存收款码、等待支付并关闭收款单。 |
| `app` | `.\server.py` | Flask 服务入口，启动后提供 `POST /create`，按 `server.py` 顶部配置加载窗口、密钥、输出目录和 webhook 参数。 |

## UI 获取模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `get_process_component_info()` | `.\utools\ui\inspector.py` | 获取指定窗口/进程的组件树，优先走 UIA，失败时回退 Win32。支持按 PID、窗口标题、顶级窗口 hwnd 精确匹配。 |
| `find_windows_by_title()` | `.\utools\ui\inspector.py` | 按顶级窗口标题查找窗口信息和 PID。 |
| `_collect_by_uia()` | `.\utools\ui\inspector.py` | UIA 后端采集入口，返回顶级窗口和组件列表。 |
| `_find_uia_top_windows()` | `.\utools\ui\inspector.py` | 在 UIA 顶级窗口中按 PID、标题、hwnd 查找候选窗口；优先标题精确匹配，再按可用性排序，避免误选标题包含相同词语的浏览器窗口。 |
| `_uia_window_sort_key()` | `.\utools\ui\inspector.py` | 给 UIA 顶级窗口排序，优先可见、位置正常、面积大的窗口。 |
| `_walk_uia_tree()` | `.\utools\ui\inspector.py` | 递归遍历 UIA 控件树并写入组件列表。 |
| `_uia_control_to_info()` | `.\utools\ui\inspector.py` | 将 UIA 控件包装成 JSON 可序列化的组件信息。 |
| `_collect_by_win32()` | `.\utools\ui\inspector.py` | Win32 后端采集入口，用于 UIA 不可用时兜底。 |
| `_find_win32_top_windows()` | `.\utools\ui\inspector.py` | 在 Win32 顶级窗口中按 PID、标题、hwnd 查找候选窗口。 |
| `_walk_win32_tree()` | `.\utools\ui\inspector.py` | 递归遍历 Win32 子窗口。 |
| `_win32_hwnd_to_info()` | `.\utools\ui\inspector.py` | 将 Win32 hwnd 包装成 JSON 可序列化的组件信息。 |
| `_empty_result()` | `.\utools\ui\inspector.py` | 构建采集失败或空结果结构。 |
| `_safe_get()` | `.\utools\ui\inspector.py` | 安全执行无参取值函数，异常时返回默认值。 |
| `_safe_method()` | `.\utools\ui\inspector.py` | 安全调用对象方法，方法不存在或异常时返回默认值。 |
| `_rect_to_dict()` | `.\utools\ui\inspector.py` | 将 UIA/Win32 矩形对象转换为字典。 |
| `_enum_windows()` | `.\utools\ui\inspector.py` | Win32 `EnumWindows` 封装。 |
| `_get_window_pid()` | `.\utools\ui\inspector.py` | 获取 hwnd 对应进程 PID。 |
| `_get_window_text()` | `.\utools\ui\inspector.py` | 获取 hwnd 窗口标题文本。 |
| `_get_class_name()` | `.\utools\ui\inspector.py` | 获取 hwnd 窗口类名。 |
| `_get_window_rect()` | `.\utools\ui\inspector.py` | 获取 hwnd 窗口坐标和尺寸。 |
| `_count_direct_win32_children()` | `.\utools\ui\inspector.py` | 统计 hwnd 的直接子窗口数量。 |

## UI 操作模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `find_first_uia_top_window()` | `.\utools\ui\operator.py` | 找到首个可用 UIA 顶级窗口；遇到隐藏壳窗口时回退到同 PID 的可见窗口。 |
| `is_usable_top_window()` | `.\utools\ui\operator.py` | 判断顶级窗口是否可见、尺寸有效、位置正常。 |
| `iter_uia_tree()` | `.\utools\ui\operator.py` | 以栈方式遍历 UIA 控件树。 |
| `uia_text_blob()` | `.\utools\ui\operator.py` | 汇总控件的 name、window_text、value，作为查找文本。 |
| `uia_control_search_info()` | `.\utools\ui\operator.py` | 获取用于遍历搜索的轻量 UIA 信息，不读取子节点计数并避免重复读取文本和值，用于降低创建流程扫描耗时。 |
| `find_uia_click_target()` | `.\utools\ui\operator.py` | 按文本查找最合适的可点击控件；先用 UIA 原生精确标题查询，再回退递归文本扫描，并优先 Button、精确文本、小面积控件。 |
| `_find_exact_title_controls()` | `.\utools\ui\operator.py` | 内部辅助，优先使用 UIA 原生精确标题查询控件，减少 Python 递归遍历。 |
| `_control_text_contains()` | `.\utools\ui\operator.py` | 内部辅助，按需读取控件名称、文本和值；文本未命中时不读取矩形和可见性等昂贵属性。 |
| `enable_fast_timings()` | `.\utools\ui\operator.py` | 降低 pywinauto 默认动作等待时间，用于加快点击、聚焦、键盘输入。 |
| `click_relative()` | `.\utools\ui\operator.py` | 只读取控件矩形并按相对坐标点击，不采集完整子树；适合小程序内部不暴露标准控件的区域，金额数字键盘依赖它。 |
| `click_screen_point()` | `.\utools\ui\operator.py` | 点击指定屏幕坐标；等待支付时用于点击匹配到的订单卡片文本位置。 |
| `invoke_or_click()` | `.\utools\ui\operator.py` | 优先使用 UIA InvokePattern 操作标准控件，失败时回退到鼠标点击；用于减少对活动桌面的依赖。 |
| `paste_text()` | `.\utools\ui\operator.py` | 用剪贴板向当前焦点控件粘贴文本，可选择先全选清空；订单号填写依赖它。 |
| `send_keys_to_control()` | `.\utools\ui\operator.py` | 聚焦目标窗口后发送键盘按键；保留为通用键盘操作能力。 |
| `set_clipboard_text()` | `.\utools\ui\operator.py` | 使用 Windows Unicode 剪贴板 API 写入文本。 |
| `wait_for_visible_uia_text()` | `.\utools\ui\operator.py` | 在指定窗口内等待可见文本出现。 |
| `uia_tree_has_visible_text()` | `.\utools\ui\operator.py` | 判断控件树中是否有可见、非 Document、尺寸有效的目标文本；优先 UIA 精确标题查询，未命中再递归扫描；`exact_title_only=True` 时跳过递归兜底。 |

## UI 截图模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `capture_relative_crop()` | `.\utools\ui\screenshot.py` | 对目标窗口截图并按相对比例裁剪保存，同时返回暗色像素占比等最终图片视觉指标。 |
| `inspect_relative_crop_visual_metrics()` | `.\utools\ui\screenshot.py` | 截取相对区域但不保存，返回暗色像素占比和平均灰度，用于等待二维码动态内容加载。 |
| `analyze_image_visual_metrics()` | `.\utools\ui\screenshot.py` | 统计 PIL 图片的暗色像素占比、平均灰度和像素数。 |
| `capture_control_visual_probe()` | `.\utools\ui\screenshot.py` | 截取目标窗口并缩小为灰度像素探针，用于低开销判断点击前后页面是否明显变化。 |
| `compare_control_visual_probes()` | `.\utools\ui\screenshot.py` | 比较两个视觉探针，返回超过像素差阈值的变化像素比例。 |
| `_get_control_rectangle()` | `.\utools\ui\screenshot.py` | 获取目标控件矩形，用于截图裁剪计算。 |
| `_get_relative_crop_box()` | `.\utools\ui\screenshot.py` | 根据窗口矩形和相对比例计算有效裁剪框。 |
| `_crop_box_to_dict()` | `.\utools\ui\screenshot.py` | 将裁剪框转换为可序列化的矩形字典。 |

## 微信收款单业务模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `open_create_pay_order_page()` | `.\utools\wechat\pay_order.py` | 自动找到“微信收款单”窗口，点击“发起收款”，等待进入“创建收款单”界面，并返回动作结果。 |
| `generate_pay_order()` | `.\utools\wechat\pay_order.py` | 自动进入创建页、填写金额/订单号并保存收款码；返回各阶段和总耗时。可选择是否继续返回主界面、等待支付并关闭收款单。 |
| `fill_create_pay_order_fields()` | `.\utools\wechat\pay_order.py` | 在已打开的创建收款单界面内填写金额和订单号。 |
| `submit_create_pay_order()` | `.\utools\wechat\pay_order.py` | 点击“创建”，等待“已创建”弹窗出现。 |
| `generate_and_capture_qr_code()` | `.\utools\wechat\pay_order.py` | 点击“生成收款码”，进入分享图页面后等待二维码纹理连续两帧达到阈值，保存后再次复检；占位图会删除并按配置重试。 |
| `_wait_for_qr_card_ready()` | `.\utools\wechat\pay_order.py` | 轮询二维码裁剪区视觉指标，只有连续达到暗色像素阈值才判定二维码已加载。 |
| `return_to_wait_payment_page()` | `.\utools\wechat\pay_order.py` | 在截图保存后返回两次，等待目标订单出现“暂无人付款”或“已支付”；API 会在二维码响应返回后于后台执行此步骤。 |
| `wait_paid_then_close_pay_order()` | `.\utools\wechat\pay_order.py` | 在主界面通过“重新进入小程序”刷新；窗口短暂重建且 UIA 枚举不到时会持续重试。目标订单号与状态同卡片匹配时优先采用；列表未显示订单号时允许页面唯一明确状态兜底。达到 `max_payment_refresh_count`（默认 5）次时调用 `on_failed`；读取或刷新发生异常时调用 `on_status_error`。两种失败路径都会继续尝试通过目标订单 UIA 元素进入详情并关闭删除，不使用固定坐标误点其他页面。 |
| `refresh_wait_payment_page()` | `.\utools\wechat\pay_order.py` | 点击右上角小程序菜单，再点击“重新进入小程序”，用于等待支付期间刷新主界面；点击后立即丢弃旧 UIA `root`，从空对象重新获取界面信息，等待订单状态加载完成并返回新窗口对象。 |
| `wait_order_status_loaded()` | `.\utools\wechat\pay_order.py` | 等待主界面加载出明确状态；优先匹配目标订单卡片，订单号未暴露时允许页面唯一的“暂无人付款”或“已支付”兜底，仅有其他文本或状态冲突时继续轮询并在超时后输出诊断。 |
| `_wait_for_visible_text_reacquiring()` | `.\utools\wechat\pay_order.py` | 等待指定文本出现；先检查当前有效窗口，未命中且达到间隔后才按窗口标题/PID 重新获取 UIA 对象。 |
| `_capture_payment_detail_visual_probe()` | `.\utools\wechat\pay_order.py` | 内部辅助，安全捕获详情页切换前后的窗口视觉探针；截图不可用时返回 `None` 并继续使用 UIA 判断。 |
| `_wait_for_payment_detail_after_order_click()` | `.\utools\wechat\pay_order.py` | 内部辅助，首次点击未进入详情时强制重新获取窗口并重新读取目标订单状态和元素矩形后重试；使用 UIA“收款记录”标题或稳定后的视觉变化确认切页，并排除列表页点击反馈。 |
| `_is_order_list_page_text()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据列表标题、发起收款、目标订单号和状态摘要判断当前是否仍停留在收款单列表。 |
| `_validate_payment_detail_before_close()` | `.\utools\wechat\pay_order.py` | 内部辅助，关闭前排除列表页、创建收款单页和生成分享图页，避免后续动作落到“发起收款”等无关元素。 |
| `_wait_for_order_deleted()` | `.\utools\wechat\pay_order.py` | 内部辅助，确认删除后已回到收款单列表，且目标订单号已经从可见 UIA 文本中消失。 |
| `_wait_for_text_to_disappear_reacquiring()` | `.\utools\wechat\pay_order.py` | 等待指定弹窗文本消失；先检查当前有效窗口，必要时才重新获取；确认文本以精确标题暴露时可跳过递归全树扫描，用于关闭/删除完成后立即继续。 |
| `_reacquire_pay_order_root()` | `.\utools\wechat\pay_order.py` | 内部辅助，当前窗口矩形仍有效时直接复用，否则按窗口标题重新获取 UIA 顶级窗口；PID 失效时回退为按标题查找。微信重建 UIA 窗口期间会在限定时间内轮询，持续不可用时抛出 `PayOrderWindowUnavailableError` 交由等待流程重试。 |
| `_control_has_valid_rectangle()` | `.\utools\wechat\pay_order.py` | 内部辅助，判断旧窗口对象是否仍有可用矩形，作为重新获取失败时的兜底。 |
| `PayOrderWindowUnavailableError` | `.\utools\wechat\pay_order.py` | 微信收款单窗口在限定时间内仍无法通过 UIA 重新获取时使用的内部异常类型，供支付等待和界面轮询流程判定为可重试状态。 |
| `_collect_visible_uia_snapshot()` | `.\utools\wechat\pay_order.py` | 内部辅助，按 `order_status_uia_max_depth`（默认 16）一次遍历收集订单状态识别所需的可见文本和矩形，供订单号、支付状态和卡片匹配复用，避免重复扫描 UIA 树。 |
| `_read_order_payment_status()` | `.\utools\wechat\pay_order.py` | 内部辅助，读取订单状态，返回 `unpaid`、`paid` 或 `unknown`；支持独立文本矩形和非整页的合并卡片容器。优先匹配目标订单卡片；订单号未显示时，仅有“已支付”返回已支付，仅有“暂无人付款”返回未支付；其他文本或两种状态同时命中时返回未知。 |
| `_find_paid_order_card_click_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据订单号和“已支付”文本的可见矩形位置判断目标订单卡片，并返回点击点。 |
| `_find_order_status_card_click_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据订单号和指定状态文本判断是否处于同一张订单卡片，并返回该状态文本中心点。 |
| `_find_smallest_control_containing_texts()` | `.\utools\wechat\pay_order.py` | 内部辅助，查找同时包含订单号和状态文本的最小可见 UIA 容器，用于兼容刷新后被合并的订单卡片。 |
| `_collect_visible_uia_text()` | `.\utools\wechat\pay_order.py` | 内部辅助，收集窗口中包括 `Document` 在内的可见 UIA 文本，供订单状态兜底识别和诊断。 |
| `_rectangle_covers_root()` | `.\utools\wechat\pay_order.py` | 内部辅助，判断候选文本容器是否接近整个窗口，避免把整页容器中心当成订单卡片。 |
| `_relative_screen_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，在 UIA 只暴露整页文本时计算订单卡片的相对屏幕点击点，不直接执行点击。 |
| `_find_visible_text_rects()` | `.\utools\wechat\pay_order.py` | 内部辅助，从状态快照提取包含指定文本的可见控件矩形，并按面积从小到大排序；调用方排除覆盖整窗的聚合容器后选择卡片点击点。 |
| `_looks_like_same_order_card()` | `.\utools\wechat\pay_order.py` | 内部辅助，判断订单号文本和已支付文本是否像处于同一张订单卡片。 |
| `_rect_center()` | `.\utools\wechat\pay_order.py` | 内部辅助，计算矩形中心点。 |
| `_point_above_rect()` | `.\utools\wechat\pay_order.py` | 内部辅助，从状态文本矩形向上偏移到订单卡片主体，避免点击不响应的底部状态行。 |
| `_click_order_card_element_or_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，优先读取订单号 UIA 元素的实时矩形并点击元素中心，元素不可用时才使用已识别的订单卡片点。 |
| `_click_required_uia_text_element()` | `.\utools\wechat\pay_order.py` | 内部辅助，操作关闭/确认/删除/更多操作等必需 UIA 文本元素；找不到元素时直接停止，不执行坐标兜底。 |
| `_click_generate_qr_button()` | `.\utools\wechat\pay_order.py` | 内部辅助，读取“生成收款码”UIA 元素的实时矩形并真实点击元素中心；找不到元素时才按配置坐标兜底，并返回点击方式。 |
| `_click_labeled_input_or_relative()` | `.\utools\wechat\pay_order.py` | 内部辅助，点击带标签的输入区域，优先查找标签附近的 `Edit`/`ComboBox` 控件，找不到再按相对坐标兜底。 |
| `_find_edit_control_near_text()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据标签文本寻找同一行附近的可见输入控件。 |
| `_click_any_text_or_relative()` | `.\utools\wechat\pay_order.py` | 内部辅助，按一组候选文本查找并点击 UIA 控件，全部失败时按相对坐标兜底。 |
| `_click_text_or_relative()` | `.\utools\wechat\pay_order.py` | 内部点击辅助，优先按 UIA 文本点击，失败时按窗口相对坐标兜底。 |
| `_click_text_or_relative_with_info()` | `.\utools\wechat\pay_order.py` | 内部点击辅助，和 `_click_text_or_relative()` 类似，但会返回目标控件信息和点击方式。 |
| `_click_uia_control_center()` | `.\utools\wechat\pay_order.py` | 内部辅助，点击 UIA 控件并返回控件中心点、控件信息和实际点击方式；可指定强制真实鼠标点击元素中心，处理小程序 UIA Invoke 无效的控件。 |
| `_fill_amount_by_keypad()` | `.\utools\wechat\pay_order.py` | 点击金额区域后，通过小程序数字键盘坐标输入金额。 |
| `_validate_amount_text()` | `.\utools\wechat\pay_order.py` | 校验金额只能包含数字和一个小数点，并且至少包含一个数字。 |
| `_open_create_pay_order_page()` | `.\utools\wechat\pay_order.py` | 内部函数，返回创建收款单页面根控件和动作结果。 |
| `_require_non_empty()` | `.\utools\wechat\pay_order.py` | 校验金额、订单号等必填参数不为空。 |
| `_make_qr_output_path()` | `.\utools\wechat\pay_order.py` | 根据订单号生成安全的收款码截图文件路径。 |

## 组件常量模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `WechatPayOrderComponents` | `.\utools\components\wechat_pay_order.py` | 保存微信收款单窗口标题、按钮文案、输入/订单卡片/菜单/裁剪区域坐标，以及元素优先点击、生成收款码重试、订单状态 UIA 扫描深度、重进次数上限、订单卡片失败后的窗口重读重试与视觉判定参数；关闭删除坐标快速模式默认关闭。 |
| `DEFAULT_PID` | `.\utools\components\wechat_pay_order.py` | 默认 PID，当前为 `None`，表示自动查找。 |
| `DEFAULT_WINDOW_TITLE` | `.\utools\components\wechat_pay_order.py` | 默认窗口标题，当前为“微信收款单”。 |
| `WECHAT_PAY_ORDER` | `.\utools\components\wechat_pay_order.py` | 默认的 `WechatPayOrderComponents` 实例。 |

## IO 模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `output_json_result()` | `.\utools\io\json_output.py` | 打印 JSON，并在指定路径写入输出文件；会自动创建输出目录。 |
| `file_to_base64()` | `.\utools\io\file_base64.py` | 读取本地收款码图片并返回纯 base64 字符串，用于 `/create` 返回 `pay_qrcode`。 |
| `remove_file_if_exists()` | `.\utools\io\file_base64.py` | 支付完成 webhook 回调后删除本地收款码图片；文件不存在时返回 `False`。 |

## API 服务模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `PayServerConfig` | `.\utools\api\pay_server.py` | Flask 支付服务配置，包含密钥、窗口、输出、等待支付、Webhook、`/create` 短等待、pending 重试间隔和默认预计创建时间。 |
| `_PayOrderJob` | `.\utools\api\pay_server.py` | 内部队列任务对象，保存订单参数、入队/开始时间、任务状态、二维码结果和创建完成事件。 |
| `_PayOrderQueueWorker` | `.\utools\api\pay_server.py` | 单线程订单 worker；截图编码后立即唤醒请求，随后后台等待支付。维护近期平均创建耗时和任务状态，为 pending 与 `/estimate` 提供预计时间。 |
| `_PayOrderQueueWorker.estimate()` | `.\utools\api\pay_server.py` | 返回目标订单或新订单的状态、队列位置、预计等待时间和建议重试间隔。 |
| `_PayOrderQueueWorker._queue_position()` | `.\utools\api\pay_server.py` | 获取指定任务在待处理队列中的位置。 |
| `create_app()` | `.\utools\api\pay_server.py` | 创建 Flask app，并注册 `POST /create` 端点。 |
| `create_order()` | `.\utools\api\pay_server.py` | `/create` 端点处理函数；在短等待内生成成功则返回二维码和 `reused` 标记，超时则返回 `code=2`、预计时间和建议重试间隔；相同订单号复用已有任务。 |
| `estimate_order()` | `.\utools\api\pay_server.py` | `POST /estimate` 端点处理函数，使用与 `/create` 相同的验签方式返回预计时间，不创建订单。 |
| `_wait_paid_webhook_and_cleanup()` | `.\utools\api\pay_server.py` | 队列 worker 内部调用；识别支付成功后发送 `TRADE_SUCCESS`，达到重进上限后发送 `TRADE_FAILED`，读取或刷新状态异常时发送 `TRADE_ERROR`；回调后继续尝试关闭删除并清理失效二维码。 |
| `_post_payment_webhook()` | `.\utools\api\pay_server.py` | 向请求传入的 webhook 地址 POST 已签名的支付结果通知；使用 webhook 公钥加密 `trade_no+total_amount+trade_status` 生成 `sign`，状态可为 `TRADE_SUCCESS`、`TRADE_FAILED` 或 `TRADE_ERROR`。 |
| `_validate_create_payload()` | `.\utools\api\pay_server.py` | 校验 `/create` 请求必填参数：`pid`、`amount`、`timestamp`、`webhook`、`sign`。 |
| `_verify_create_payload()` | `.\utools\api\pay_server.py` | 统一解析并验证 `/create`、`/estimate` 请求参数及 RSA 签名。 |
| `_error()` | `.\utools\api\pay_server.py` | 构建统一错误 JSON。 |

## Epay 插件

| 函数 | 文件地址 | 作用 |
| --- | --- | --- |
| `check()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 支付页轮询接口；返回当前订单 `waiting`、`paid`、`failed` 或 `error` 状态。 |
| `renderQrImagePage()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 渲染带倒计时和付款状态轮询的二维码页面；成功自动返回，失败、异常或超时后停止检测并提示关闭页面重新下单。 |
| `paymentFailureStatePath()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 生成订单支付失败临时状态文件路径。 |
| `markPaymentFailed()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 收到 `TRADE_FAILED` 或 `TRADE_ERROR` Webhook 后写入失败或异常状态，供当前支付页检测。 |
| `getPaymentFailureStatus()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 查询两小时内有效的支付失败或状态异常标记。 |
| `clearPaymentFailure()` | `.\Epay\LemonWXPhone\LemonWXPhone.php` | 真正创建新任务或支付成功时清理旧失败状态。 |

## 安全签名模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `ensure_rsa_keypair()` | `.\utools\security\rsa_cipher.py` | 确保 RSA 私钥/公钥存在；首次启动服务时可自动生成。 |
| `verify_encrypted_signature()` | `.\utools\security\rsa_cipher.py` | 用服务端私钥解密 `sign`，并与 `pid+amount+timestamp` 做恒定时间比较。 |
| `encrypt_text_with_public_key()` | `.\utools\security\rsa_cipher.py` | 用 RSA 公钥加密文本并返回 base64 密文；Webhook 签名使用它。 |
| `decrypt_sign_text()` | `.\utools\security\rsa_cipher.py` | 解密 base64/base64url 的 RSA 密文，支持 OAEP-SHA256、OAEP-SHA1 和 PKCS1v15。 |
