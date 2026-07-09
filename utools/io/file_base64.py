# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import os


def file_to_base64(path: str) -> str:
    """读取本地文件并返回纯 base64 字符串."""

    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode("ascii")


def remove_file_if_exists(path: str) -> bool:
    """删除本地文件；文件不存在时返回 False."""

    if not path or not os.path.exists(path):
        return False
    os.remove(path)
    return True
