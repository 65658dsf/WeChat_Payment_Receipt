# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from utools.api.pay_server import PayServerConfig, create_app
from utools.components.wechat_pay_order import DEFAULT_WINDOW_TITLE


# ===== Flask 服务配置 =====
HOST = "127.0.0.1"
PORT = 5000
DEBUG = False

# 第一次启动会自动生成 keys/private_key.pem 和 keys/public_key.pem。
# 客户端用 public_key.pem 加密 pid+amount+timestamp，得到 sign。
PRIVATE_KEY_PATH = r"keys\private_key.pem"
PUBLIC_KEY_PATH = r"keys\public_key.pem"

# Webhook 回调用全新的密钥对。
# 服务端用 webhook_public_key.pem 加密 trade_no+total_amount+trade_status。
# 客户端用 webhook_private_key.pem 解密 webhook 的 sign。
WEBHOOK_PRIVATE_KEY_PATH = r"keys\webhook_private_key.pem"
WEBHOOK_PUBLIC_KEY_PATH = r"keys\webhook_public_key.pem"
AUTO_CREATE_KEYPAIR = True

# 微信收款单窗口配置；None 表示按窗口标题自动查找。
WINDOW_PID: Optional[int] = None
WINDOW_TITLE = DEFAULT_WINDOW_TITLE

# 运行输出和等待配置。
QR_OUTPUT_DIR = r"outputs"
CREATE_TIMEOUT_SECONDS = 8.0
WAIT_PAID_TIMEOUT_SECONDS: Optional[float] = None
WEBHOOK_TIMEOUT_SECONDS = 8.0
WEBHOOK_RETRY_COUNT = 3


app = create_app(
    PayServerConfig(
        private_key_path=PRIVATE_KEY_PATH,
        public_key_path=PUBLIC_KEY_PATH,
        webhook_private_key_path=WEBHOOK_PRIVATE_KEY_PATH,
        webhook_public_key_path=WEBHOOK_PUBLIC_KEY_PATH,
        auto_create_keypair=AUTO_CREATE_KEYPAIR,
        window_pid=WINDOW_PID,
        window_title=WINDOW_TITLE,
        qr_output_dir=QR_OUTPUT_DIR,
        create_timeout_seconds=CREATE_TIMEOUT_SECONDS,
        wait_paid_timeout_seconds=WAIT_PAID_TIMEOUT_SECONDS,
        webhook_timeout_seconds=WEBHOOK_TIMEOUT_SECONDS,
        webhook_retry_count=WEBHOOK_RETRY_COUNT,
    )
)


if __name__ == "__main__":
    print(f"Flask 服务已启动: http://{HOST}:{PORT}")
    print(f"公钥路径: {PUBLIC_KEY_PATH}")
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)
