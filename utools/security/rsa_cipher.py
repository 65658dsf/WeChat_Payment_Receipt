# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hmac
import os
from typing import Iterable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def ensure_rsa_keypair(private_key_path: str, public_key_path: str) -> None:
    """确保 RSA 私钥/公钥文件存在；不存在时自动生成一组."""

    if os.path.exists(private_key_path) and os.path.exists(public_key_path):
        return

    output_dir = os.path.dirname(private_key_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    with open(private_key_path, "wb") as file:
        file.write(private_bytes)
    with open(public_key_path, "wb") as file:
        file.write(public_bytes)


def verify_encrypted_signature(
    sign: str,
    expected_plaintext: str,
    private_key_path: str,
) -> bool:
    """解密 sign，并与 pid+amount+timestamp 原文做恒定时间比较."""

    decrypted = decrypt_sign_text(sign, private_key_path)
    return hmac.compare_digest(decrypted, expected_plaintext)


def decrypt_sign_text(sign: str, private_key_path: str) -> str:
    encrypted = _decode_sign_base64(sign)
    private_key = _load_private_key(private_key_path)

    last_error: Exception | None = None
    for rsa_padding in _supported_paddings():
        try:
            decrypted = private_key.decrypt(encrypted, rsa_padding)
            return decrypted.decode("utf-8")
        except Exception as exc:
            last_error = exc

    raise ValueError(f"sign 解密失败: {last_error}")


def _load_private_key(private_key_path: str):
    with open(private_key_path, "rb") as file:
        return serialization.load_pem_private_key(file.read(), password=None)


def _decode_sign_base64(sign: str) -> bytes:
    text = sign.strip()
    padding_length = (-len(text)) % 4
    padded = text + ("=" * padding_length)
    try:
        return base64.b64decode(padded, validate=True)
    except Exception:
        return base64.urlsafe_b64decode(padded)


def _supported_paddings() -> Iterable[padding.AsymmetricPadding]:
    return (
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
        ),
        padding.PKCS1v15(),
    )
