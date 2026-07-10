# 微信收款单服务端接入说明

本文说明如何接入本项目提供的 Flask 服务端。

## 1. 启动服务

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
python server.py
```

默认地址：

```text
http://127.0.0.1:5000
```

可通过环境变量 `WECHAT_PAY_SERVER_HOST` 和 `WECHAT_PAY_SERVER_PORT` 临时覆盖监听地址和端口；默认仍为 `0.0.0.0:5000`。

服务启动后会自动生成 RSA 密钥文件：

```text
keys/private_key.pem
keys/public_key.pem
keys/webhook_private_key.pem
keys/webhook_public_key.pem
```

`keys/*.pem` 已加入 `.gitignore`，不要提交到代码仓库。

## 2. 密钥用途

创建订单请求签名：

| 文件 | 持有方 | 用途 |
| --- | --- | --- |
| `keys/public_key.pem` | 接入方客户端 | 加密 `pid+amount+timestamp`，生成 `/create` 请求里的 `sign` |
| `keys/private_key.pem` | 服务端 | 解密 `/create` 请求里的 `sign` 并校验 |

Webhook 回调签名：

| 文件 | 持有方 | 用途 |
| --- | --- | --- |
| `keys/webhook_public_key.pem` | 服务端 | 加密 `trade_no+total_amount+trade_status`，生成 webhook 里的 `sign` |
| `keys/webhook_private_key.pem` | 接入方客户端 | 解密 webhook 里的 `sign` 并校验 |

加密默认使用 RSA OAEP SHA256。

## 3. 创建订单接口

接口：

```text
POST /create
```

完整地址示例：

```text
http://127.0.0.1:5000/create
```

请求 JSON：

```json
{
  "pid": "XZN202612354",
  "amount": "0.01",
  "timestamp": "1698524800000",
  "webhook": "https://example.com/webhook",
  "sign": "base64后的RSA加密数据"
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `pid` | 是 | 商户订单号；服务端会作为 `trade_no` 返回 |
| `amount` | 是 | 收款金额，字符串格式，例如 `"0.01"` |
| `timestamp` | 是 | 时间戳字符串，建议毫秒时间戳 |
| `webhook` | 是 | 支付成功后的回调地址 |
| `sign` | 是 | 使用 `keys/public_key.pem` 加密 `pid+amount+timestamp` 后得到的 base64 字符串 |

签名原文拼接方式：

```text
pid + amount + timestamp
```

示例：

```text
XZN2026123540.011698524800000
```

注意：不是用 `+` 字符连接，而是直接拼接字符串。

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

`pay_qrcode` 是纯 base64 图片数据，不带 `data:image/png;base64,` 前缀。

二维码尚未准备好时会提前返回，HTTP 状态仍为 `200`：

```json
{
  "code": 2,
  "msg": "pending",
  "data": {
    "trade_no": "XZN202612354",
    "status": "CREATING",
    "ready": false,
    "queue_position": 0,
    "estimated_wait_seconds": 6,
    "retry_after_seconds": 5,
    "waiting_for_previous_payment": false
  }
}
```

客户端收到 `code=2` 后，应等待 `retry_after_seconds`，然后使用相同订单号重新调用 `/create`。服务端会复用已有任务，不会重复创建收款单。

失败响应示例：

```json
{
  "code": 0,
  "msg": "sign 校验失败",
  "data": null
}
```

当前服务一次只操作一个微信收款单流程；如果已有订单正在等待支付，新的 `/create` 请求会进入队列等待。轮到该请求时才会创建收款单并返回二维码；如果在 `/create` 的同步等待上限内尚未完成，服务会先返回 HTTP 200、`code=2`，客户端应按 `retry_after_seconds` 使用同一订单号重试。

订单开始创建后，服务端会在二维码截图保存和 base64 编码完成后立即返回响应；返回微信主界面、等待支付、Webhook 和图片清理均在后台继续执行。代理或 CDN 的源站响应超时应大于服务端配置的 `/create` 同步等待上限，否则客户端可能在收到 `code=2` 前先被代理断开。

如果多次请求使用相同的 `pid`，并且该订单仍在排队、创建中或等待支付中，服务端会直接复用该订单，不会重复创建微信收款单；请求会返回同一个订单号对应的二维码。状态识别时，只要页面能读到有效文本且不包含“暂无人付款”，即按已支付通过。支付成功后会优先读取目标订单号元素的实时矩形并点击卡片；若未切页，会重新获取微信收款单窗口、重新扫描目标订单和状态元素，再使用新的实时矩形重试，不沿用旧坐标偏移。关闭、确认、删除和更多操作必须读取对应 UIA 文本元素后执行，找不到元素时终止，最终还要确认目标订单已从列表消失。等待支付期间连续重新进入小程序达到 5 次且明确仍为“暂无人付款”时，服务端不会发送成功 Webhook，而是进入订单详情关闭并删除收款单，清理失效二维码后释放后台任务；页面完全读不到文本时继续刷新。后续使用相同 `pid` 调用 `/create` 会重新创建收款单。

### 3.1 预计时间接口

```text
POST /estimate
```

请求 JSON 和签名方法与 `/create` 完全相同。该接口不会创建订单，只返回当前订单或新订单的预计状态：

```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "trade_no": "XZN202612354",
    "status": "QUEUED",
    "ready": false,
    "queue_position": 1,
    "estimated_wait_seconds": 15,
    "retry_after_seconds": 5,
    "waiting_for_previous_payment": true
  }
}
```

`estimated_wait_seconds` 根据近期创建耗时计算。若 `waiting_for_previous_payment=true`，前一笔订单的实际付款时间不可预测，该值只能作为最短预计时间，客户端应以 `retry_after_seconds` 作为轮询间隔。

## 4. Python 生成 /create sign 示例

```python
import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


public_key_path = r"keys\public_key.pem"
trade_no = "XZN202612354"
amount = "0.01"
timestamp = str(int(time.time() * 1000))

with open(public_key_path, "rb") as file:
    public_key = serialization.load_pem_public_key(file.read())

plain = f"{trade_no}{amount}{timestamp}".encode("utf-8")
encrypted = public_key.encrypt(
    plain,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    ),
)
sign = base64.b64encode(encrypted).decode("ascii")

payload = {
    "pid": trade_no,
    "amount": amount,
    "timestamp": timestamp,
    "webhook": "http://127.0.0.1:5001/webhook",
    "sign": sign,
}

response = requests.post("http://127.0.0.1:5000/create", json=payload, timeout=60)
print(response.status_code)
print(response.json())
```

## 5. Webhook 回调

识别到支付成功后，服务端会立即向请求中的 `webhook` 地址发送回调；回调完成后再继续关闭和删除微信收款单：

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

Webhook 签名原文：

```text
trade_no + total_amount + trade_status
```

示例：

```text
XZN2026123540.01TRADE_SUCCESS
```

客户端需要用 `keys/webhook_private_key.pem` 解密 webhook 的 `sign`，并与上述原文比对。

微信小程序重建窗口导致 UIA 短暂不可用时，后台任务会重新按窗口标题获取窗口并继续等待，不会立即判定订单失败。支付成功时，Webhook 发送成功后服务端才会清理本地二维码图片；Webhook 最终失败时保留图片用于排查。达到重进次数上限且仍未支付时不会发送成功 Webhook，关闭删除收款单成功后会清理失效二维码。

## 6. Python 校验 Webhook sign 示例

```python
from utools.security.rsa_cipher import verify_encrypted_signature


payload = {
    "code": 1,
    "msg": "success",
    "data": {
        "trade_no": "XZN202612354",
        "total_amount": "0.01",
        "trade_status": "TRADE_SUCCESS",
    },
    "sign": "base64数据",
}

data = payload["data"]
expected = f"{data['trade_no']}{data['total_amount']}{data['trade_status']}"

ok = verify_encrypted_signature(
    sign=payload["sign"],
    expected_plaintext=expected,
    private_key_path=r"keys\webhook_private_key.pem",
)
print(ok)
```

## 7. 本地联调

项目已提供测试脚本：

```bash
python test.py
```

测试脚本会：

1. 启动本地 webhook：`http://127.0.0.1:5001/webhook`
2. 使用 `keys/public_key.pem` 生成 `/create` 请求签名
3. 调用 `http://127.0.0.1:5000/create`
4. 等待支付成功 webhook
5. 使用 `keys/webhook_private_key.pem` 校验 webhook 签名

注意：运行 `python test.py` 会真实触发微信创建收款单流程。

## 8. 支付完成后的服务端行为

支付成功后服务端会：

1. 识别到目标订单已支付
2. POST 带签名的 webhook
3. 进入微信收款记录详情
4. 关闭收款单并确认关闭
5. 再次打开更多操作
6. 删除收款单并确认删除
7. Webhook 成功后删除本地二维码图片

如果 webhook 多次发送失败，本地二维码图片会保留，便于排查问题。

如果连续重新进入小程序达到 5 次且明确读取到“暂无人付款”，服务端会将该次支付判定为失败，进入订单详情执行关闭和删除，不发送成功 Webhook，并在清理失效二维码后释放任务。页面完全读不到文本时继续刷新，直到读到文本或达到整体支付等待超时。
