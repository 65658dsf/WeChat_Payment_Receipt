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
    dark_pixel_threshold: int = 96,
) -> Dict[str, Any]:
    """截图控件区域，并按相对比例裁剪保存."""

    crop_box = _get_relative_crop_box(
        control,
        left_ratio,
        top_ratio,
        right_ratio,
        bottom_ratio,
    )
    image = ImageGrab.grab(bbox=crop_box)
    visual_metrics = analyze_image_visual_metrics(image, dark_pixel_threshold)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    image.save(output_path)

    return {
        "output_path": output_path,
        "crop_box": _crop_box_to_dict(crop_box),
        "visual_metrics": visual_metrics,
    }


def inspect_relative_crop_visual_metrics(
    control: Any,
    left_ratio: float,
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
    dark_pixel_threshold: int = 96,
) -> Dict[str, Any]:
    """读取相对裁剪区视觉指标但不保存图片，用于等待动态内容加载完成."""

    crop_box = _get_relative_crop_box(
        control,
        left_ratio,
        top_ratio,
        right_ratio,
        bottom_ratio,
    )
    image = ImageGrab.grab(bbox=crop_box)
    return {
        "crop_box": _crop_box_to_dict(crop_box),
        **analyze_image_visual_metrics(image, dark_pixel_threshold),
    }


def analyze_image_visual_metrics(
    image: Any,
    dark_pixel_threshold: int = 96,
) -> Dict[str, Any]:
    """统计图片暗色像素占比；二维码比加载占位具有明显更高的暗色密度."""

    threshold = max(1, min(254, int(dark_pixel_threshold)))
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    total_pixels = sum(histogram)
    if total_pixels <= 0:
        raise ValueError("图片像素为空，无法计算视觉指标.")
    dark_pixels = sum(histogram[: threshold + 1])
    mean_grayscale = sum(index * count for index, count in enumerate(histogram)) / total_pixels
    return {
        "dark_pixel_threshold": threshold,
        "dark_pixel_ratio": round(dark_pixels / total_pixels, 6),
        "mean_grayscale": round(mean_grayscale, 3),
        "total_pixels": total_pixels,
    }


def capture_control_visual_probe(
    control: Any,
    sample_width: int = 72,
    sample_height: int = 112,
) -> Dict[str, Any]:
    """截取窗口并缩小为灰度像素，用于快速判断界面是否发生明显变化."""

    if sample_width <= 0 or sample_height <= 0:
        raise ValueError("视觉探针尺寸必须大于 0.")

    rectangle = _get_control_rectangle(control)
    left = rectangle["left"]
    top = rectangle["top"]
    image = ImageGrab.grab(
        bbox=(
            left,
            top,
            left + rectangle["width"],
            top + rectangle["height"],
        )
    )
    grayscale = image.convert("L").resize((sample_width, sample_height))
    return {
        "width": sample_width,
        "height": sample_height,
        "pixels": grayscale.tobytes(),
    }


def compare_control_visual_probes(
    before: Dict[str, Any],
    after: Dict[str, Any],
    pixel_difference_threshold: int = 18,
) -> float:
    """返回两次视觉探针中变化像素所占比例，范围为 0.0 到 1.0."""

    before_size = (int(before.get("width") or 0), int(before.get("height") or 0))
    after_size = (int(after.get("width") or 0), int(after.get("height") or 0))
    if before_size != after_size or before_size[0] <= 0 or before_size[1] <= 0:
        raise ValueError("视觉探针尺寸不一致.")

    before_pixels = bytes(before.get("pixels") or b"")
    after_pixels = bytes(after.get("pixels") or b"")
    if len(before_pixels) != len(after_pixels) or not before_pixels:
        raise ValueError("视觉探针像素数据无效.")

    threshold = max(1, min(255, int(pixel_difference_threshold)))
    changed_count = sum(
        1
        for before_pixel, after_pixel in zip(before_pixels, after_pixels)
        if abs(before_pixel - after_pixel) >= threshold
    )
    return changed_count / len(before_pixels)


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


def _get_relative_crop_box(
    control: Any,
    left_ratio: float,
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
) -> tuple[int, int, int, int]:
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
    if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
        raise RuntimeError("相对截图区域无效，无法裁剪.")
    return crop_box


def _crop_box_to_dict(crop_box: tuple[int, int, int, int]) -> Dict[str, int]:
    return {
        "left": crop_box[0],
        "top": crop_box[1],
        "right": crop_box[2],
        "bottom": crop_box[3],
        "width": crop_box[2] - crop_box[0],
        "height": crop_box[3] - crop_box[1],
    }
