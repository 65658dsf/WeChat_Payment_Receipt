# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request

from utools.components.wechat_pay_order import DEFAULT_WINDOW_TITLE
from utools.io.file_base64 import file_to_base64, remove_file_if_exists
from utools.security.rsa_cipher import (
    encrypt_text_with_public_key,
    ensure_rsa_keypair,
    verify_encrypted_signature,
)
from utools.wechat.pay_order import generate_pay_order, wait_paid_then_close_pay_order


@dataclass(frozen=True)
class PayServerConfig:
    private_key_path: str = r"keys\private_key.pem"
    public_key_path: str = r"keys\public_key.pem"
    webhook_private_key_path: str = r"keys\webhook_private_key.pem"
    webhook_public_key_path: str = r"keys\webhook_public_key.pem"
    auto_create_keypair: bool = True
    window_pid: Optional[int] = None
    window_title: str = DEFAULT_WINDOW_TITLE
    qr_output_dir: str = "outputs"
    create_timeout_seconds: float = 8.0
    wait_paid_timeout_seconds: Optional[float] = None
    webhook_timeout_seconds: float = 8.0
    webhook_retry_count: int = 3


@dataclass
class _PayOrderJob:
    trade_no: str
    amount: str
    webhook: str
    created_event: threading.Event = field(default_factory=threading.Event)
    response: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    qr_path: str = ""


class _PayOrderQueueWorker:
    def __init__(self, config: PayServerConfig) -> None:
        self._config = config
        self._queue: Queue[_PayOrderJob] = Queue()
        self._active_jobs: Dict[str, _PayOrderJob] = {}
        self._active_jobs_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, trade_no: str, amount: str, webhook: str) -> tuple[_PayOrderJob, bool, int]:
        with self._active_jobs_lock:
            existing_job = self._active_jobs.get(trade_no)
            if existing_job is not None:
                return existing_job, True, self._queue.qsize()

            job = _PayOrderJob(trade_no=trade_no, amount=amount, webhook=webhook)
            self._active_jobs[trade_no] = job
            queue_size = self._enqueue(job)
            return job, False, queue_size

    def _enqueue(self, job: _PayOrderJob) -> int:
        self._queue.put(job)
        return self._queue.qsize()

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._process_job(job)
            except Exception as exc:
                job.error = exc
                job.created_event.set()
                traceback.print_exc()
            finally:
                if job.error is not None:
                    self._forget_job(job)
                self._queue.task_done()

    def _process_job(self, job: _PayOrderJob) -> None:
        qr_path = ""
        try:
            action_result = generate_pay_order(
                amount=job.amount,
                order_no=job.trade_no,
                pid=self._config.window_pid,
                window_title=self._config.window_title,
                timeout_seconds=self._config.create_timeout_seconds,
                save_qr_code=True,
                qr_output_dir=self._config.qr_output_dir,
                return_to_wait_page=True,
                wait_paid_and_close=False,
            )
            qr_info = action_result.get("qr_code") or {}
            qr_path = str(qr_info.get("output_path") or "")
            job.qr_path = qr_path
            pay_qrcode = file_to_base64(qr_path)
            job.response = {
                "code": 1,
                "msg": "success",
                "data": {
                    "trade_no": job.trade_no,
                    "pay_qrcode": pay_qrcode,
                },
            }
            job.created_event.set()
        except Exception as exc:
            job.error = exc
            job.created_event.set()
            raise

        _wait_paid_webhook_and_cleanup(
            config=self._config,
            trade_no=job.trade_no,
            amount=job.amount,
            webhook=job.webhook,
            qr_path=qr_path,
        )
        self._forget_job(job)

    def _forget_job(self, job: _PayOrderJob) -> None:
        with self._active_jobs_lock:
            if self._active_jobs.get(job.trade_no) is job:
                del self._active_jobs[job.trade_no]


def create_app(config: PayServerConfig) -> Flask:
    if config.auto_create_keypair:
        ensure_rsa_keypair(config.private_key_path, config.public_key_path)
        ensure_rsa_keypair(config.webhook_private_key_path, config.webhook_public_key_path)

    app = Flask(__name__)
    order_worker = _PayOrderQueueWorker(config)
    order_worker.start()

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

        job, reused, queue_size = order_worker.submit(trade_no, amount, webhook)
        if reused:
            print(f"复用已有订单二维码: {trade_no}", flush=True)
        else:
            print(f"订单已进入队列: {trade_no}, 当前队列长度: {queue_size}", flush=True)
        job.created_event.wait()

        if job.error is not None:
            return jsonify(_error(f"创建收款单失败: {job.error}")), 500
        return jsonify(job.response)

    return app


def _wait_paid_webhook_and_cleanup(
    config: PayServerConfig,
    trade_no: str,
    amount: str,
    webhook: str,
    qr_path: str,
) -> None:
    webhook_sent = False
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
            webhook_public_key_path=config.webhook_public_key_path,
            timeout_seconds=config.webhook_timeout_seconds,
            retry_count=config.webhook_retry_count,
        )
        webhook_sent = True
    except Exception:
        traceback.print_exc()
    finally:
        if webhook_sent:
            remove_file_if_exists(qr_path)


def _post_payment_success_webhook(
    webhook: str,
    trade_no: str,
    amount: str,
    webhook_public_key_path: str,
    timeout_seconds: float,
    retry_count: int,
) -> None:
    trade_status = "TRADE_SUCCESS"
    body = {
        "code": 1,
        "msg": "success",
        "data": {
            "trade_no": trade_no,
            "total_amount": amount,
            "trade_status": trade_status,
        },
    }
    body["sign"] = encrypt_text_with_public_key(
        f"{trade_no}{amount}{trade_status}",
        webhook_public_key_path,
    )
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
