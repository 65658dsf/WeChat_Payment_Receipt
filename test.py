# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import threading
import time
from typing import Any, Dict

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from utools.security.rsa_cipher import verify_encrypted_signature


# ===== 测试配置 =====
PAY_SERVER_CREATE_URL = "http://198.18.0.13:12150/create"
PAY_SERVER_ESTIMATE_URL = PAY_SERVER_CREATE_URL.rsplit("/", 1)[0] + "/estimate"
PUBLIC_KEY_PATH = r"keys\public_key.pem"
WEBHOOK_PRIVATE_KEY_PATH = r"keys\webhook_private_key.pem"

WEBHOOK_HOST = "127.0.0.1"
WEBHOOK_PORT = 5001
WEBHOOK_URL = f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook"

TRADE_NO = "XZN202612354"
AMOUNT = "0.01"

CREATE_REQUEST_TIMEOUT_SECONDS = 60
WAIT_WEBHOOK_TIMEOUT_SECONDS = 600


app = Flask(__name__)
webhook_received = threading.Event()
webhook_payloads: list[Dict[str, Any]] = []


@app.post("/webhook")
def webhook():
    payload = request.get_json(silent=True) or {}
    webhook_payloads.append(payload)
    print("收到 webhook:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    data = payload.get("data") or {}
    trade_no = str(data.get("trade_no") or "")
    total_amount = str(data.get("total_amount") or "")
    status = str(data.get("trade_status") or "").strip()
    sign = str(payload.get("sign") or "")
    expected_sign_text = f"{trade_no}{total_amount}{status}"

    try:
        sign_ok = verify_encrypted_signature(
            sign=sign,
            expected_plaintext=expected_sign_text,
            private_key_path=WEBHOOK_PRIVATE_KEY_PATH,
        )
    except Exception as exc:
        print(f"webhook sign 解密失败: {exc}", flush=True)
        return jsonify({"code": 0, "msg": "sign 解密失败"})

    if not sign_ok:
        print("webhook sign 校验失败", flush=True)
        return jsonify({"code": 0, "msg": "sign 校验失败"})

    if status == "TRADE_SUCCESS":
        print("支付成功", flush=True)
        webhook_received.set()
        return jsonify({"code": 1, "msg": "success"})
    if status == "TRADE_FAILED":
        print("支付失败，可重新打开订单", flush=True)
        webhook_received.set()
        return jsonify({"code": 1, "msg": "payment_failed"})
    if status == "TRADE_ERROR":
        print("订单状态异常，可重新打开订单", flush=True)
        webhook_received.set()
        return jsonify({"code": 1, "msg": "order_status_error"})

    return jsonify({"code": 0, "msg": "未知支付状态"})


class LocalWebhookServer:
    def __init__(self, host: str, port: int) -> None:
        self._server = make_server(host, port, app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=3)


def build_rsa_sign(public_key_path: str, trade_no: str, amount: str, timestamp: str) -> str:
    """用公钥加密 trade_no+amount+timestamp，并返回 base64 sign."""

    with open(public_key_path, "rb") as file:
        public_key = serialization.load_pem_public_key(file.read())

    plaintext = f"{trade_no}{amount}{timestamp}".encode("utf-8")
    encrypted = public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode("ascii")


def build_create_payload() -> Dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    return {
        "pid": TRADE_NO,
        "amount": AMOUNT,
        "timestamp": timestamp,
        "webhook": WEBHOOK_URL,
        "sign": build_rsa_sign(PUBLIC_KEY_PATH, TRADE_NO, AMOUNT, timestamp),
    }


def post_json(url: str, payload: Dict[str, str]) -> Dict[str, Any]:
    response = requests.post(url, json=payload, timeout=CREATE_REQUEST_TIMEOUT_SECONDS)
    print(f"{url} HTTP {response.status_code}")
    data = response.json()
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])
    response.raise_for_status()
    return data


def create_order() -> Dict[str, Any]:
    attempt = 0
    while True:
        attempt += 1
        payload = build_create_payload()

        print(f"第 {attempt} 次发送 /create 请求:")
        print(json.dumps({**payload, "sign": payload["sign"][:32] + "..."}, ensure_ascii=False, indent=2))
        data = post_json(PAY_SERVER_CREATE_URL, payload)
        if int(data.get("code") or 0) != 2:
            return data

        pending = data.get("data") or {}
        estimate = post_json(PAY_SERVER_ESTIMATE_URL, payload)
        print("当前预计时间:")
        print(json.dumps(estimate.get("data") or {}, ensure_ascii=False, indent=2))
        retry_after = max(1, int(pending.get("retry_after_seconds") or 5))
        print(f"二维码仍在生成，{retry_after} 秒后重试 /create...")
        time.sleep(retry_after)


def main() -> None:
    server = LocalWebhookServer(WEBHOOK_HOST, WEBHOOK_PORT)
    server.start()
    print(f"本地 webhook 已启动: {WEBHOOK_URL}")

    try:
        result = create_order()
        if result.get("code") != 1:
            raise RuntimeError(f"创建订单失败: {result}")

        print(f"等待 webhook，最多 {WAIT_WEBHOOK_TIMEOUT_SECONDS} 秒...")
        if not webhook_received.wait(WAIT_WEBHOOK_TIMEOUT_SECONDS):
            raise TimeoutError("等待 webhook 超时.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
