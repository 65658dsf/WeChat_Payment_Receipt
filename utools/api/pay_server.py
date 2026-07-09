# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
import traceback
import math
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
from utools.wechat.pay_order import (
    generate_pay_order,
    return_to_wait_payment_page,
    wait_paid_then_close_pay_order,
)


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
    create_request_wait_seconds: float = 10.0
    pending_retry_after_seconds: int = 5
    default_create_estimate_seconds: float = 15.0


@dataclass
class _PayOrderJob:
    trade_no: str
    amount: str
    webhook: str
    created_event: threading.Event = field(default_factory=threading.Event)
    response: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    qr_path: str = ""
    queued_at: float = field(default_factory=time.perf_counter)
    started_at: float = 0.0
    state: str = "queued"


class _PayOrderQueueWorker:
    def __init__(self, config: PayServerConfig) -> None:
        self._config = config
        self._queue: Queue[_PayOrderJob] = Queue()
        self._active_jobs: Dict[str, _PayOrderJob] = {}
        self._active_jobs_lock = threading.Lock()
        self._average_creation_seconds = max(1.0, config.default_create_estimate_seconds)
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
                job.state = "failed"
                job.created_event.set()
                traceback.print_exc()
            finally:
                if job.error is not None:
                    self._forget_job(job)
                self._queue.task_done()

    def _process_job(self, job: _PayOrderJob) -> None:
        qr_path = ""
        job.state = "creating"
        job.started_at = time.perf_counter()
        queue_wait_seconds = round(time.perf_counter() - job.queued_at, 3)
        print(
            f"开始创建订单: {job.trade_no}, 队列等待: {queue_wait_seconds}秒",
            flush=True,
        )
        try:
            action_result = generate_pay_order(
                amount=job.amount,
                order_no=job.trade_no,
                pid=self._config.window_pid,
                window_title=self._config.window_title,
                timeout_seconds=self._config.create_timeout_seconds,
                save_qr_code=True,
                qr_output_dir=self._config.qr_output_dir,
                return_to_wait_page=False,
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
            creation_seconds = max(0.001, time.perf_counter() - job.started_at)
            with self._active_jobs_lock:
                self._average_creation_seconds = (
                    self._average_creation_seconds * 0.7 + creation_seconds * 0.3
                )
                job.state = "waiting_payment"
            job.created_event.set()
            timings = action_result.get("timings_seconds") or {}
            print(
                f"订单二维码已生成并返回: {job.trade_no}, "
                f"队列等待: {queue_wait_seconds}秒, 分段耗时: {timings}",
                flush=True,
            )
        except Exception as exc:
            job.error = exc
            job.created_event.set()
            raise

        try:
            return_to_wait_payment_page(
                root=None,
                order_no=job.trade_no,
                timeout_seconds=self._config.create_timeout_seconds,
                pid=self._config.window_pid,
                window_title=self._config.window_title,
            )
        except Exception as exc:
            print(
                f"二维码已返回，但自动返回等待付款页面失败，将通过重进小程序恢复: {exc}",
                flush=True,
            )

        _wait_paid_webhook_and_cleanup(
            config=self._config,
            trade_no=job.trade_no,
            amount=job.amount,
            webhook=job.webhook,
            qr_path=qr_path,
        )
        self._forget_job(job)

    def estimate(self, trade_no: str) -> Dict[str, Any]:
        with self._active_jobs_lock:
            job = self._active_jobs.get(trade_no)
            active_jobs = list(self._active_jobs.values())
            average_seconds = self._average_creation_seconds

        retry_after = max(1, int(self._config.pending_retry_after_seconds))
        if job is None:
            would_queue = len(active_jobs) > 0
            return {
                "trade_no": trade_no,
                "status": "WOULD_QUEUE" if would_queue else "AVAILABLE",
                "ready": False,
                "queue_position": len(active_jobs),
                "estimated_wait_seconds": int(math.ceil(average_seconds * (len(active_jobs) + 1))),
                "retry_after_seconds": retry_after,
                "waiting_for_previous_payment": any(
                    item.state == "waiting_payment" for item in active_jobs
                ),
            }

        if job.response is not None and job.error is None:
            return {
                "trade_no": trade_no,
                "status": "READY",
                "ready": True,
                "queue_position": 0,
                "estimated_wait_seconds": 0,
                "retry_after_seconds": 0,
                "waiting_for_previous_payment": False,
            }

        queue_position = self._queue_position(job)
        waiting_for_previous_payment = any(
            item is not job and item.state == "waiting_payment" for item in active_jobs
        )
        if job.state == "creating" and job.started_at > 0:
            elapsed = time.perf_counter() - job.started_at
            estimated_wait = max(1, int(math.ceil(average_seconds - elapsed)))
        else:
            estimated_wait = max(
                retry_after,
                int(math.ceil(average_seconds * max(1, queue_position))),
            )

        return {
            "trade_no": trade_no,
            "status": job.state.upper(),
            "ready": False,
            "queue_position": queue_position,
            "estimated_wait_seconds": estimated_wait,
            "retry_after_seconds": retry_after,
            "waiting_for_previous_payment": waiting_for_previous_payment,
        }

    def _queue_position(self, job: _PayOrderJob) -> int:
        with self._queue.mutex:
            queued_jobs = list(self._queue.queue)
        for index, queued_job in enumerate(queued_jobs, start=1):
            if queued_job is job:
                return index
        return 0

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
        verified, error = _verify_create_payload(payload, config)
        if error:
            return jsonify(_error(error)), 400

        trade_no = verified["trade_no"]
        amount = verified["amount"]
        webhook = verified["webhook"]

        job, reused, queue_size = order_worker.submit(trade_no, amount, webhook)
        if reused:
            print(f"复用已有订单二维码: {trade_no}", flush=True)
        else:
            print(f"订单已进入队列: {trade_no}, 当前队列长度: {queue_size}", flush=True)
        created = job.created_event.wait(timeout=max(0.1, config.create_request_wait_seconds))
        if not created:
            return jsonify(
                {
                    "code": 2,
                    "msg": "pending",
                    "data": order_worker.estimate(trade_no),
                }
            )

        if job.error is not None:
            return jsonify(_error(f"创建收款单失败: {job.error}")), 500
        return jsonify(job.response)

    @app.post("/estimate")
    def estimate_order():
        payload = request.get_json(silent=True) or {}
        verified, error = _verify_create_payload(payload, config)
        if error:
            return jsonify(_error(error)), 400
        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": order_worker.estimate(verified["trade_no"]),
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


def _verify_create_payload(
    payload: Dict[str, Any],
    config: PayServerConfig,
) -> tuple[Optional[Dict[str, str]], str]:
    error = _validate_create_payload(payload)
    if error:
        return None, error

    trade_no = str(payload["pid"])
    amount = str(payload["amount"])
    timestamp = str(payload["timestamp"])
    webhook = str(payload["webhook"])
    sign = str(payload["sign"])
    try:
        sign_ok = verify_encrypted_signature(
            sign=sign,
            expected_plaintext=f"{trade_no}{amount}{timestamp}",
            private_key_path=config.private_key_path,
        )
    except Exception as exc:
        return None, f"sign 解密失败: {exc}"
    if not sign_ok:
        return None, "sign 校验失败"
    return {
        "trade_no": trade_no,
        "amount": amount,
        "timestamp": timestamp,
        "webhook": webhook,
    }, ""


def _error(message: str) -> Dict[str, Any]:
    return {
        "code": 0,
        "msg": message,
        "data": None,
    }
