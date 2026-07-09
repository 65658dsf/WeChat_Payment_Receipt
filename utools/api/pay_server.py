# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request

from utools.components.wechat_pay_order import DEFAULT_WINDOW_TITLE
from utools.io.file_base64 import file_to_base64, remove_file_if_exists
from utools.security.rsa_cipher import ensure_rsa_keypair, verify_encrypted_signature
from utools.wechat.pay_order import generate_pay_order, wait_paid_then_close_pay_order


@dataclass(frozen=True)
class PayServerConfig:
    private_key_path: str = r"keys\private_key.pem"
    public_key_path: str = r"keys\public_key.pem"
    auto_create_keypair: bool = True
    window_pid: Optional[int] = None
    window_title: str = DEFAULT_WINDOW_TITLE
    qr_output_dir: str = "outputs"
    create_timeout_seconds: float = 8.0
    wait_paid_timeout_seconds: Optional[float] = None
    webhook_timeout_seconds: float = 8.0
    webhook_retry_count: int = 3


_ORDER_LOCK = threading.Lock()


def create_app(config: PayServerConfig) -> Flask:
    if config.auto_create_keypair:
        ensure_rsa_keypair(config.private_key_path, config.public_key_path)

    app = Flask(__name__)

    @app.post("/create")
    def create_order():
        payload = request.get_json(silent=True) or {}
        error = _validate_create_payload(payload)
        if error:
            return jsonify(_error(error)), 400

        trade_no = str(payload["pid"])
        amount = str(payload["amount"])
        timestamp = str(payload["timestamp"])
        webhook = str(payload["webhook"])
        sign = str(payload["sign"])

        expected_sign_text = f"{trade_no}{amount}{timestamp}"
        try:
            sign_ok = verify_encrypted_signature(
                sign=sign,
                expected_plaintext=expected_sign_text,
                private_key_path=config.private_key_path,
            )
        except Exception as exc:
            return jsonify(_error(f"sign 解密失败: {exc}")), 400
        if not sign_ok:
            return jsonify(_error("sign 校验失败")), 400

        if not _ORDER_LOCK.acquire(blocking=False):
            return jsonify(_error("当前已有订单正在等待支付，请稍后再试")), 429

        qr_path = ""
        try:
            action_result = generate_pay_order(
                amount=amount,
                order_no=trade_no,
                pid=config.window_pid,
                window_title=config.window_title,
                timeout_seconds=config.create_timeout_seconds,
                save_qr_code=True,
                qr_output_dir=config.qr_output_dir,
                return_to_wait_page=True,
                wait_paid_and_close=False,
            )
            qr_info = action_result.get("qr_code") or {}
            qr_path = str(qr_info.get("output_path") or "")
            pay_qrcode = file_to_base64(qr_path)
        except Exception as exc:
            _ORDER_LOCK.release()
            traceback.print_exc()
            return jsonify(_error(f"创建收款单失败: {exc}")), 500

        worker = threading.Thread(
            target=_wait_paid_webhook_and_cleanup,
            args=(config, trade_no, amount, webhook, qr_path),
            daemon=True,
        )
        worker.start()

        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": {
                    "trade_no": trade_no,
                    "pay_qrcode": pay_qrcode,
                },
            }
        )

    return app


def _wait_paid_webhook_and_cleanup(
    config: PayServerConfig,
    trade_no: str,
    amount: str,
    webhook: str,
    qr_path: str,
) -> None:
    try:
        wait_paid_then_close_pay_order(
            root=None,
            order_no=trade_no,
            pid=config.window_pid,
            window_title=config.window_title,
            timeout_seconds=config.wait_paid_timeout_seconds,
        )
        print("支付成功", flush=True)
        _post_payment_success_webhook(
            webhook=webhook,
            trade_no=trade_no,
            amount=amount,
            timeout_seconds=config.webhook_timeout_seconds,
            retry_count=config.webhook_retry_count,
        )
    except Exception:
        traceback.print_exc()
    finally:
        try:
            remove_file_if_exists(qr_path)
        finally:
            _ORDER_LOCK.release()


def _post_payment_success_webhook(
    webhook: str,
    trade_no: str,
    amount: str,
    timeout_seconds: float,
    retry_count: int,
) -> None:
    body = {
        "code": 1,
        "msg": "success",
        "data": {
            "trade_no": trade_no,
            "total_amount": amount,
            "trade_status": "TRADE_SUCCESS",
        },
    }
    last_error: Exception | None = None
    for _ in range(max(1, retry_count)):
        try:
            response = requests.post(webhook, json=body, timeout=timeout_seconds)
            response.raise_for_status()
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Webhook 回调失败: {last_error}")


def _validate_create_payload(payload: Dict[str, Any]) -> str:
    required_fields = ["pid", "amount", "timestamp", "webhook", "sign"]
    for field in required_fields:
        if field not in payload or str(payload[field]).strip() == "":
            return f"缺少参数: {field}"
    return ""


def _error(message: str) -> Dict[str, Any]:
    return {
        "code": 0,
        "msg": message,
        "data": None,
    }
