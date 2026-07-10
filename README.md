# 微信收款单自动化服务

本项目用于在 Windows 桌面环境中自动操作微信小程序窗口“微信收款单”，完成创建收款单、截图收款码、等待支付、关闭并删除收款单等流程，并提供 Flask API 给外部系统创建订单。

## 功能概览

- 自动查找窗口标题为“微信收款单”的进程。
- 自动点击“发起收款”，填写金额和订单号。
- 自动创建收款单并生成收款码截图。
- 将收款码图片返回为 base64。
- 返回主界面等待付款。
- 每轮通过“右上角三个点 -> 重新进入小程序”刷新状态。
- 读取目标订单状态：`暂无人付款` 或 `已支付`。
- 识别到支付成功后立即向 webhook 发送带签名通知，再点击目标订单卡片主体进入收款记录，完成关闭、确认关闭、删除和确认删除。订单卡片首次点击未进入详情时，会强制重新获取微信收款单窗口、重新扫描目标订单和状态元素，再使用新的实时矩形重试；不沿用旧窗口坐标做偏移点击。
- 微信重建小程序窗口导致 UIA 短暂不可用时自动重试；只要页面能读到有效文本且不包含“暂无人付款”，即按已支付通过。重新进入小程序达到 5 次且明确仍为“暂无人付款”时，当前后台任务会判定支付失败，进入订单详情完成关闭和删除后释放任务；页面完全读不到文本时继续刷新。
- Webhook 成功，或支付失败且收款单已关闭删除后，删除本地二维码图片。
- 多个 `/create` 请求会按顺序排队处理，不会因为已有订单等待支付而直接拒绝。
- 相同订单号重复调用 `/create` 时，会复用已有订单二维码，不会重复创建收款单。

## 环境要求

- Windows 系统
- Python 3.10+
- 微信 PC 端可正常打开对应小程序窗口
- 小程序窗口标题包含：`微信收款单`
- 必须在已登录、未锁屏、RDP 未断开的交互式桌面运行；不要作为 Windows 服务或在无活动桌面的会话中运行

安装依赖：

```bash
pip install -r requirements.txt
```

## 直接运行自动化

编辑 [main.py](./main.py) 顶部配置：

```python
Generator_PayOrder = True
Generator_PayOrder_Amount = "0.01"
Generator_PayOrder_OrderNo = "ORDER001"
Generator_PayOrder_SaveQRCode = True
Generator_PayOrder_ReturnToWaitPage = True
Generator_PayOrder_WaitPaidAndClose = True
```

运行：

```bash
python main.py
```

注意：这会真实操作微信界面并创建收款单。

## 启动 API 服务

运行：

```bash
python server.py
```

默认服务地址：

```text
http://127.0.0.1:5000
```

需要临时使用其他监听地址或端口时，可设置 `WECHAT_PAY_SERVER_HOST` 和 `WECHAT_PAY_SERVER_PORT` 环境变量；未设置时仍使用上述默认值。

创建订单接口：

```text
POST /create
```

详细接入说明见：

[API_INTEGRATION.md](./API_INTEGRATION.md)

## API 简述

请求示例：

```json
{
  "pid": "XZN202612354",
  "amount": "0.01",
  "timestamp": "1698524800000",
  "webhook": "https://example.com/webhook",
  "sign": "base64后的RSA加密数据"
}
```

`sign` 生成规则：

```text
pid + amount + timestamp
```

客户端使用：

```text
keys/public_key.pem
```

对上述原文进行 RSA 加密，得到请求里的 `sign`。

成功响应：

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "trade_no": "XZN202612354",
    "pay_qrcode": "base64数据"
  }
}
```

## Webhook 回调

支付成功后服务端会 POST：

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "trade_no": "XZN202612354",
    "total_amount": "0.01",
    "trade_status": "TRADE_SUCCESS"
  },
  "sign": "base64数据"
}
```

Webhook 的 `sign` 生成规则：

```text
trade_no + total_amount + trade_status
```

服务端使用：

```text
keys/webhook_public_key.pem
```

加密上述原文。客户端使用：

```text
keys/webhook_private_key.pem
```

解密并比对。

## 本地测试

项目提供 [test.py](./test.py)：

```bash
python test.py
```

测试脚本会：

- 启动本地 webhook：`http://127.0.0.1:5001/webhook`
- 用 `keys/public_key.pem` 生成 `/create` 请求签名
- 调用本地 `/create`
- 等待支付成功 webhook
- 用 `keys/webhook_private_key.pem` 校验 webhook 签名

注意：运行测试脚本会真实触发微信创建收款单。

## 密钥文件

首次启动服务会自动生成：

```text
keys/private_key.pem
keys/public_key.pem
keys/webhook_private_key.pem
keys/webhook_public_key.pem
```

说明：

| 文件 | 用途 |
| --- | --- |
| `keys/public_key.pem` | 客户端生成 `/create` 请求 sign |
| `keys/private_key.pem` | 服务端校验 `/create` 请求 sign |
| `keys/webhook_public_key.pem` | 服务端生成 webhook sign |
| `keys/webhook_private_key.pem` | 客户端校验 webhook sign |

`keys/*.pem` 已加入 `.gitignore`，不要提交私钥。

## 目录结构

```text
.
├── main.py                         # 本地自动化入口
├── server.py                       # Flask API 服务入口
├── test.py                         # 本地 API + webhook 测试脚本
├── API_INTEGRATION.md              # 外部系统接入说明
├── requirements.txt
├── utools
│   ├── api
│   │   └── pay_server.py           # API、Webhook、后台等待支付逻辑
│   ├── components
│   │   ├── COMPONENTS.md           # Agent 组件索引
│   │   └── wechat_pay_order.py     # 微信收款单坐标、文案和等待参数
│   ├── io
│   │   ├── file_base64.py          # 图片 base64 和文件清理
│   │   └── json_output.py
│   ├── security
│   │   └── rsa_cipher.py           # RSA 加密、解密和验签
│   ├── ui
│   │   ├── inspector.py            # UI 组件树采集
│   │   ├── operator.py             # 通用 UI 操作
│   │   └── screenshot.py           # 截图裁剪
│   └── wechat
│       └── pay_order.py            # 微信收款单业务流程
└── outputs                         # 运行生成文件，已忽略提交
```

## 维护说明

- UI 坐标、按钮文案和等待时间主要维护在 [utools/components/wechat_pay_order.py](./utools/components/wechat_pay_order.py)。
- 微信业务流程主要维护在 [utools/wechat/pay_order.py](./utools/wechat/pay_order.py)。
- API 和 webhook 逻辑主要维护在 [utools/api/pay_server.py](./utools/api/pay_server.py)。
- 函数索引需要同步维护：[utools/components/COMPONENTS.md](./utools/components/COMPONENTS.md)。

## 注意事项

- 本项目依赖当前微信小程序 UI 布局，微信版本或页面布局变化后，坐标可能需要微调。
- 由于金额键盘、菜单和部分小程序区域需要真实鼠标坐标点击，运行服务的 Windows 会话必须保持活动桌面。任务计划程序启动时请使用“仅当用户登录时运行”。
- API 服务创建并保存二维码截图、完成 base64 编码后会立即返回 `/create`，返回主界面和等待支付在后台继续执行。`/create` 最多同步等待 10 秒，未完成时返回 `code=2` 与 `retry_after_seconds`，客户端等待后重试同一订单；`POST /estimate` 可查询队列位置和预计时间。服务一次只操作一个订单流程，相同订单号会复用活跃任务和二维码。控制台会输出创建、等待付款、Webhook、关闭/删除和图片清理等阶段耗时，便于定位慢步骤。
- `outputs/` 和 `keys/*.pem` 已忽略提交。
- 支付成功时 Webhook 发送成功后删除本地二维码图片；如果 webhook 失败，图片会保留用于排查。达到重进次数上限且未支付时，收款单关闭删除成功后也会清理已失效的二维码图片。
- 关闭、确认、删除和更多操作默认必须找到对应 UIA 文本元素后再执行，不使用可能误点“发起收款”的固定坐标；进入关闭流程前还会排除列表页、创建页和生成分享图页面。只有最终回到收款单列表且目标订单号已经消失，才返回 `closed=true`、`deleted=true`。
