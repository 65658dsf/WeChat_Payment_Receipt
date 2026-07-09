# AGENTS.md

## 基本约定

- 本项目运行在 Windows 环境。
- 回复用户时使用中文。
- 读写、编辑、查看项目文件时优先使用 Node.js 脚本方式，不使用 PowerShell 的 `Get-Content`、`Set-Content` 等文件读写命令。
- Python 代码默认使用 UTF-8 编码。
- 修改 Python 功能后至少运行：

```bash
python -m py_compile main.py utools/ui/inspector.py utools/ui/operator.py utools/ui/screenshot.py utools/wechat/pay_order.py utools/components/wechat_pay_order.py utools/io/json_output.py
```

## 目录职责

- `main.py`：主入口，只放运行配置和流程编排。
- `server.py`：Flask 服务入口，提供 `POST /create` 接口。
- `utools/api/pay_server.py`：API 层，负责请求校验、创建收款单、返回二维码、后台等待支付、Webhook 回调和清理本地图片。
- `utools/security/rsa_cipher.py`：RSA 非对称加密 sign 解密和校验。
- `utools/ui/inspector.py`：获取窗口、进程和 UI 组件树信息。
- `utools/ui/operator.py`：通用 UIA 界面操作能力，例如查找可点击控件、等待文本出现。
- `utools/ui/screenshot.py`：按窗口相对比例截图和裁剪保存。
- `utools/wechat/pay_order.py`：微信收款单业务动作，例如进入“创建收款单”界面。
- `utools/components/wechat_pay_order.py`：微信收款单相关标题、按钮文案等组件常量。
- `utools/components/COMPONENTS.md`：给 Agent 阅读的函数索引，记录函数功能和文件位置。新增、移动、删除函数时必须同步更新。
- `utools/io/json_output.py`：JSON 输出和输出目录创建。
- `outputs/`：运行输出文件目录。
- `keys/`：RSA 密钥目录，`*.pem` 已加入 `.gitignore`，不要提交私钥。

## 维护原则

- 获取界面信息的逻辑放在 `utools/ui/inspector.py`。
- 操作界面控件的通用逻辑放在 `utools/ui/operator.py`。
- 微信收款单专属流程放在 `utools/wechat/pay_order.py`。
- 文案、标题、按钮名等可复用组件常量放在 `utools/components/`。
- 不要把业务动作堆进 `main.py`；`main.py` 只保留配置和调用顺序。
- 如果后续新增动作，例如填写金额、填写说明、点击创建，请优先新增到 `utools/wechat/pay_order.py`，底层通用控件查找能力复用 `utools/ui/operator.py`。
- 当前微信小程序页面内的金额/说明输入框不稳定暴露为标准 `Edit` 控件。`fast_input_coordinate_mode=True` 时直接使用已维护的相对坐标点击两个自绘输入区，避免一次 UIA 输入框扫描耗时十几秒；金额数字通过小程序键盘坐标输入，订单号通过剪贴板粘贴。关闭快速模式后才尝试标签附近的输入控件。
- 界面操作默认优先读取 UIA 元素、文本和输入控件，例如“创建”“生成收款码”“收款说明”“返回”等；只有小程序未暴露标准控件或点击失败时，才使用 `utools/components/wechat_pay_order.py` 里的窗口相对坐标兜底。
- 标准 UIA 控件优先使用 `invoke_or_click()`，减少真实鼠标依赖；但金额数字键盘和部分小程序自绘区域仍可能需要坐标点击，必须在已登录、未锁屏、RDP 未断开的活动桌面运行。不要作为 Windows 服务或无交互桌面任务运行。
- 创建收款单完成后会读取“生成收款码”UIA 元素的实时矩形，并真实点击元素中心进入“生成分享图”页面；这里不使用可能无效果的 UIA Invoke。随后按相对比例裁剪中间白色收款码卡片保存到 `outputs/`。如果点击后没有进入“生成分享图”，会按 `generate_qr_retry_count` 重新获取窗口并重试。截图保存后默认点击左上角返回两次，回到主界面等待付款列表；检测到“已支付”后进入详情并关闭、确认、删除收款单。关闭/删除阶段不使用固定延时，而是按 `wait_poll_interval_seconds` 轮询对应元素出现或消失，界面就绪后立即执行下一步。
- 等待支付时通过右上角三个点打开小程序菜单，再点击“重新进入小程序”刷新页面；每次检查和每次重新进入后都要重新按窗口标题获取 UIA 窗口对象，避免旧 root/PID 失效。重新进入后必须等待目标订单读取到明确状态（“暂无人付款”或“已支付”）才能继续。若 `order_status_load_timeout_seconds` 内仍未读到状态，不要终止任务，应等待 `status_refresh_retry_wait_seconds` 后再次执行“重新进入小程序”，直到读取成功或整体支付等待超时。订单状态优先用订单号和状态文本的独立矩形匹配；刷新后如果微信把卡片合并成单个 UIA 容器，则匹配同时包含订单号和状态的最小容器；页面仅有一种明确状态时才允许整页文本兜底，避免多订单混合状态时误判。
- 为了速度，`amount_clear_backspace_count` 默认是 `0`，表示不预先清空金额。新打开创建页时金额为空，可在 1-2 秒内完成填写；如果反复复用同一个创建页并需要覆盖旧金额，可以把它改成 `8` 或更大。
- `wait_poll_interval_seconds`、`paste_select_wait_seconds`、`paste_after_wait_seconds` 用于控制等待速度，默认按快速操作配置。
- Flask 服务启动入口是 `python server.py`。`POST /create` 请求里的 `sign` 是客户端用 `keys/public_key.pem` 加密 `pid+amount+timestamp` 后得到的 base64/base64url 文本；服务端用 `keys/private_key.pem` 解密并比对。
- Webhook 回调使用另一组全新的密钥：服务端用 `keys/webhook_public_key.pem` 加密 `trade_no+total_amount+trade_status` 生成 webhook `sign`；客户端用 `keys/webhook_private_key.pem` 解密并比对。
- `/create` 请求验签通过后进入单线程订单队列。截图和 base64 编码完成后立即设置 `created_event`；返回主界面、等待支付、Webhook 和图片清理由后台继续执行。`/create` 只同步等待 `create_request_wait_seconds`，未完成时返回 HTTP 200、`code=2`、预计时间和 `retry_after_seconds`，客户端等待后用同一订单号重试。`POST /estimate` 使用相同签名返回预计时间但不创建任务。已有订单等待支付时新订单继续排队，相同订单号复用已有任务和二维码。

## 常用入口配置

在 `main.py` 顶部配置：

- `PID = None`：自动按窗口标题查找进程。
- `WINDOW_TITLE = DEFAULT_WINDOW_TITLE`：默认查找“微信收款单”。
- `Generator_PayOrder = True`：自动点击“发起收款”，进入“创建收款单”界面并填写金额/订单号。
- `Generator_PayOrder_Amount = "1.00"`：要填写到金额区域的金额。
- `Generator_PayOrder_OrderNo = "ORDER001"`：要填写到“收款说明”的订单号。
- `Generator_PayOrder_SaveQRCode = True`：创建后保存收款码截图。
- `Generator_PayOrder_QRCodeOutputDir = r"outputs"`：收款码截图输出目录。
- `Generator_PayOrder_ReturnToWaitPage = True`：保存收款码截图后点击左上角返回两次，回到主界面等待付款。
- `Generator_PayOrder_WaitPaidAndClose = True`：回到主界面后每秒刷新一次，看到“已支付”后进入详情并关闭收款单。
- `Generator_PayOrder_WaitPaidTimeoutSeconds = None`：等待支付的超时时间；`None` 表示一直等待。
- `FIND_ONLY = True`：只查找窗口和 PID，不采集组件树。
- `OUTPUT = r"outputs\output.json"`：保存 JSON 输出。
