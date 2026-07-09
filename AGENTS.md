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
- `utools/ui/inspector.py`：获取窗口、进程和 UI 组件树信息。
- `utools/ui/operator.py`：通用 UIA 界面操作能力，例如查找可点击控件、等待文本出现。
- `utools/ui/screenshot.py`：按窗口相对比例截图和裁剪保存。
- `utools/wechat/pay_order.py`：微信收款单业务动作，例如进入“创建收款单”界面。
- `utools/components/wechat_pay_order.py`：微信收款单相关标题、按钮文案等组件常量。
- `utools/components/COMPONENTS.md`：给 Agent 阅读的函数索引，记录函数功能和文件位置。新增、移动、删除函数时必须同步更新。
- `utools/io/json_output.py`：JSON 输出和输出目录创建。
- `outputs/`：运行输出文件目录。

## 维护原则

- 获取界面信息的逻辑放在 `utools/ui/inspector.py`。
- 操作界面控件的通用逻辑放在 `utools/ui/operator.py`。
- 微信收款单专属流程放在 `utools/wechat/pay_order.py`。
- 文案、标题、按钮名等可复用组件常量放在 `utools/components/`。
- 不要把业务动作堆进 `main.py`；`main.py` 只保留配置和调用顺序。
- 如果后续新增动作，例如填写金额、填写说明、点击创建，请优先新增到 `utools/wechat/pay_order.py`，底层通用控件查找能力复用 `utools/ui/operator.py`。
- 当前微信小程序页面内的金额/说明输入框不稳定暴露为标准 `Edit` 控件。金额通过窗口相对坐标点击小程序数字键盘输入；订单号通过窗口相对坐标点击“收款说明”后剪贴板粘贴。输入区域坐标比例维护在 `utools/components/wechat_pay_order.py`。
- 创建收款单完成后会点击“生成收款码”，进入“生成分享图”页面，并按相对比例裁剪中间白色收款码卡片保存到 `outputs/`。
- 为了速度，`amount_clear_backspace_count` 默认是 `0`，表示不预先清空金额。新打开创建页时金额为空，可在 1-2 秒内完成填写；如果反复复用同一个创建页并需要覆盖旧金额，可以把它改成 `8` 或更大。
- `wait_poll_interval_seconds`、`paste_select_wait_seconds`、`paste_after_wait_seconds` 用于控制等待速度，默认按快速操作配置。

## 常用入口配置

在 `main.py` 顶部配置：

- `PID = None`：自动按窗口标题查找进程。
- `WINDOW_TITLE = DEFAULT_WINDOW_TITLE`：默认查找“微信收款单”。
- `Generator_PayOrder = True`：自动点击“发起收款”，进入“创建收款单”界面并填写金额/订单号。
- `Generator_PayOrder_Amount = "1.00"`：要填写到金额区域的金额。
- `Generator_PayOrder_OrderNo = "ORDER001"`：要填写到“收款说明”的订单号。
- `Generator_PayOrder_SaveQRCode = True`：创建后保存收款码截图。
- `Generator_PayOrder_QRCodeOutputDir = r"outputs"`：收款码截图输出目录。
- `FIND_ONLY = True`：只查找窗口和 PID，不采集组件树。
- `OUTPUT = r"outputs\output.json"`：保存 JSON 输出。
