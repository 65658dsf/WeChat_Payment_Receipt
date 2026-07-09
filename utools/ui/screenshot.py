# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

from PIL import ImageGrab

from utools.ui.inspector import _uia_control_to_info


def capture_relative_crop(
    control: Any,
    output_path: str,
    left_ratio: float,
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
) -> Dict[str, Any]:
    """截图控件区域，并按相对比例裁剪保存."""

    rectangle = _get_control_rectangle(control)
    left = rectangle["left"]
    top = rectangle["top"]
    width = rectangle["width"]
    height = rectangle["height"]

    crop_box = (
        left + int(width * left_ratio),
        top + int(height * top_ratio),
        left + int(width * right_ratio),
        top + int(height * bottom_ratio),
    )
    image = ImageGrab.grab(bbox=crop_box)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    image.save(output_path)

    return {
        "output_path": output_path,
        "crop_box": {
            "left": crop_box[0],
            "top": crop_box[1],
            "right": crop_box[2],
            "bottom": crop_box[3],
            "width": crop_box[2] - crop_box[0],
            "height": crop_box[3] - crop_box[1],
        },
    }


def _get_control_rectangle(control: Any) -> Dict[str, int]:
    info = _uia_control_to_info(control, 0, 0, "screenshot-root")
    rectangle = info.get("rectangle") or {}
    required = ["left", "top", "width", "height"]
    if any(rectangle.get(key) is None for key in required):
        raise RuntimeError("目标窗口矩形无效，无法截图.")
    if int(rectangle.get("width") or 0) <= 0 or int(rectangle.get("height") or 0) <= 0:
        raise RuntimeError("目标窗口尺寸无效，无法截图.")
    return {
        "left": int(rectangle["left"]),
        "top": int(rectangle["top"]),
        "width": int(rectangle["width"]),
        "height": int(rectangle["height"]),
    }
