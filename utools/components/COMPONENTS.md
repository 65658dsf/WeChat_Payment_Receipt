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
| `_find_uia_top_windows()` | `.\utools\ui\inspector.py` | 在 UIA 顶级窗口中按 PID、标题、hwnd 查找候选窗口，并按可用性排序。 |
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
| `find_uia_click_target()` | `.\utools\ui\operator.py` | 按文本查找最合适的可点击控件，优先 Button、精确文本、小面积控件。 |
| `enable_fast_timings()` | `.\utools\ui\operator.py` | 降低 pywinauto 默认动作等待时间，用于加快点击、聚焦、键盘输入。 |
| `click_relative()` | `.\utools\ui\operator.py` | 按控件矩形相对坐标点击，适合小程序内部不暴露标准控件的区域；金额数字键盘依赖它。 |
| `click_screen_point()` | `.\utools\ui\operator.py` | 点击指定屏幕坐标；等待支付时用于点击匹配到的订单卡片文本位置。 |
| `paste_text()` | `.\utools\ui\operator.py` | 用剪贴板向当前焦点控件粘贴文本，可选择先全选清空；订单号填写依赖它。 |
| `send_keys_to_control()` | `.\utools\ui\operator.py` | 聚焦目标窗口后发送键盘按键；保留为通用键盘操作能力。 |
| `set_clipboard_text()` | `.\utools\ui\operator.py` | 使用 Windows Unicode 剪贴板 API 写入文本。 |
| `wait_for_visible_uia_text()` | `.\utools\ui\operator.py` | 在指定窗口内等待可见文本出现。 |
| `uia_tree_has_visible_text()` | `.\utools\ui\operator.py` | 判断控件树中是否有可见、非 Document、尺寸有效的目标文本。 |

## UI 截图模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `capture_relative_crop()` | `.\utools\ui\screenshot.py` | 对目标窗口截图，并按相对比例裁剪保存；用于保存收款码白色卡片区域。 |
| `_get_control_rectangle()` | `.\utools\ui\screenshot.py` | 获取目标控件矩形，用于截图裁剪计算。 |

## 微信收款单业务模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `open_create_pay_order_page()` | `.\utools\wechat\pay_order.py` | 自动找到“微信收款单”窗口，点击“发起收款”，等待进入“创建收款单”界面，并返回动作结果。 |
| `generate_pay_order()` | `.\utools\wechat\pay_order.py` | 自动进入“创建收款单”界面，并把金额填到金额区域、订单号填到“收款说明”；创建后可保存收款码截图、返回主界面、等待支付并关闭收款单。 |
| `fill_create_pay_order_fields()` | `.\utools\wechat\pay_order.py` | 在已打开的创建收款单界面内填写金额和订单号。 |
| `submit_create_pay_order()` | `.\utools\wechat\pay_order.py` | 点击“创建”，等待“已创建”弹窗出现。 |
| `generate_and_capture_qr_code()` | `.\utools\wechat\pay_order.py` | 点击“生成收款码”，进入分享图页面后裁剪保存中间白色收款码卡片。 |
| `return_to_wait_payment_page()` | `.\utools\wechat\pay_order.py` | 在收款码截图保存后点击左上角返回两次，并等待主界面出现“暂无人付款”。 |
| `wait_paid_then_close_pay_order()` | `.\utools\wechat\pay_order.py` | 在主界面每秒通过“重新进入小程序”刷新；每次刷新后先等待目标订单读到“暂无人付款”或“已支付”，已支付后点击订单卡片进入“收款记录”，再点击“更多操作”和“关闭收款单”，确认关闭后再次点击“更多操作”并删除收款单，最后确认删除。 |
| `refresh_wait_payment_page()` | `.\utools\wechat\pay_order.py` | 点击右上角小程序菜单，再点击“重新进入小程序”，用于等待支付期间刷新主界面；刷新后等待订单状态加载完成并返回重新获取到的窗口对象。 |
| `wait_order_status_loaded()` | `.\utools\wechat\pay_order.py` | 等待主界面加载出目标订单的明确状态，状态必须是“暂无人付款”或“已支付”。 |
| `_reacquire_pay_order_root()` | `.\utools\wechat\pay_order.py` | 内部辅助，按窗口标题重新获取当前可用 UIA 顶级窗口；PID 失效时回退为按标题查找。 |
| `_control_has_valid_rectangle()` | `.\utools\wechat\pay_order.py` | 内部辅助，判断旧窗口对象是否仍有可用矩形，作为重新获取失败时的兜底。 |
| `_read_order_payment_status()` | `.\utools\wechat\pay_order.py` | 内部辅助，读取目标订单状态，返回 `unpaid`、`paid` 或 `unknown`。 |
| `_find_paid_order_card_click_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据订单号和“已支付”文本的可见矩形位置判断目标订单卡片，并返回点击点。 |
| `_find_order_status_card_click_point()` | `.\utools\wechat\pay_order.py` | 内部辅助，根据订单号和指定状态文本判断是否处于同一张订单卡片，并返回该状态文本中心点。 |
| `_find_visible_text_rects()` | `.\utools\wechat\pay_order.py` | 内部辅助，遍历 UIA 树并提取包含指定文本的可见控件矩形。 |
| `_looks_like_same_order_card()` | `.\utools\wechat\pay_order.py` | 内部辅助，判断订单号文本和已支付文本是否像处于同一张订单卡片。 |
| `_rect_center()` | `.\utools\wechat\pay_order.py` | 内部辅助，计算矩形中心点。 |
| `_click_text_or_relative()` | `.\utools\wechat\pay_order.py` | 内部点击辅助，优先按 UIA 文本点击，失败时按窗口相对坐标兜底。 |
| `_fill_amount_by_keypad()` | `.\utools\wechat\pay_order.py` | 点击金额区域后，通过小程序数字键盘坐标输入金额。 |
| `_validate_amount_text()` | `.\utools\wechat\pay_order.py` | 校验金额只能包含数字和一个小数点，并且至少包含一个数字。 |
| `_open_create_pay_order_page()` | `.\utools\wechat\pay_order.py` | 内部函数，返回创建收款单页面根控件和动作结果。 |
| `_require_non_empty()` | `.\utools\wechat\pay_order.py` | 校验金额、订单号等必填参数不为空。 |
| `_make_qr_output_path()` | `.\utools\wechat\pay_order.py` | 根据订单号生成安全的收款码截图文件路径。 |

## 组件常量模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `WechatPayOrderComponents` | `.\utools\components\wechat_pay_order.py` | 保存微信收款单窗口标题、创建页/已创建/分享图/已支付/收款记录标题、按钮文案、输入/创建/生成收款码/返回/订单卡片/小程序菜单/重新进入小程序/更多操作/关闭收款单/确定关闭/删除收款单/确定删除/裁剪区域的窗口相对坐标，以及快速模式等待参数。 |
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
| `PayServerConfig` | `.\utools\api\pay_server.py` | Flask 支付服务配置，包含创建订单密钥路径、webhook 专用密钥路径、微信窗口标题、输出目录、等待支付超时和 webhook 重试参数。 |
| `_PayOrderJob` | `.\utools\api\pay_server.py` | 内部队列任务对象，保存订单号、金额、webhook、二维码创建结果和创建完成事件。 |
| `_PayOrderQueueWorker` | `.\utools\api\pay_server.py` | 单线程订单队列 worker，按顺序创建收款单、等待支付、发送 webhook 并清理二维码图片；维护活跃订单表，相同订单号复用已有二维码。 |
| `create_app()` | `.\utools\api\pay_server.py` | 创建 Flask app，并注册 `POST /create` 端点。 |
| `create_order()` | `.\utools\api\pay_server.py` | `/create` 端点内部处理函数：校验 JSON、解密验签，把不同订单号加入队列；相同订单号复用已有 job，并等待二维码创建后返回 base64。 |
| `_wait_paid_webhook_and_cleanup()` | `.\utools\api\pay_server.py` | 队列 worker 内部调用，等待支付成功后关闭/删除收款单，发送 webhook，并删除本地二维码图片。 |
| `_post_payment_success_webhook()` | `.\utools\api\pay_server.py` | 向请求传入的 webhook 地址 POST 支付成功通知，并用 webhook 公钥加密 `trade_no+total_amount+trade_status` 生成 `sign`。 |
| `_validate_create_payload()` | `.\utools\api\pay_server.py` | 校验 `/create` 请求必填参数：`pid`、`amount`、`timestamp`、`webhook`、`sign`。 |
| `_error()` | `.\utools\api\pay_server.py` | 构建统一错误 JSON。 |

## 安全签名模块

| 函数/类 | 文件地址 | 作用 |
| --- | --- | --- |
| `ensure_rsa_keypair()` | `.\utools\security\rsa_cipher.py` | 确保 RSA 私钥/公钥存在；首次启动服务时可自动生成。 |
| `verify_encrypted_signature()` | `.\utools\security\rsa_cipher.py` | 用服务端私钥解密 `sign`，并与 `pid+amount+timestamp` 做恒定时间比较。 |
| `encrypt_text_with_public_key()` | `.\utools\security\rsa_cipher.py` | 用 RSA 公钥加密文本并返回 base64 密文；Webhook 签名使用它。 |
| `decrypt_sign_text()` | `.\utools\security\rsa_cipher.py` | 解密 base64/base64url 的 RSA 密文，支持 OAEP-SHA256、OAEP-SHA1 和 PKCS1v15。 |
