"""图片处理工具（基于 Pillow）。

提供等比缩略图、按尺寸缩放、格式转换等通用能力。
所有函数对失败做兜底：读取失败返回 None 或抛出明确异常，避免污染业务流程。
"""

import io
from pathlib import Path
from typing import BinaryIO

from loguru import logger
from PIL import Image, UnidentifiedImageError

# 需要转为 RGB 才能保存为 JPEG 的模式
_RGB_REQUIRED_FORMATS = {"JPEG", "JPG"}


def open_image(source: str | Path | BinaryIO) -> Image.Image:
    """打开图片并加载像素数据。调用方负责关闭（推荐使用 with）。"""
    image = Image.open(source)
    image.load()
    return image


def get_image_size(source: str | Path | BinaryIO) -> tuple[int, int] | None:
    """读取图片宽高；失败返回 None（不抛出，便于业务侧容错）。"""
    try:
        with open_image(source) as image:
            return image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("读取图片尺寸失败：{}", exc)
        return None


def make_thumbnail(
    source: str | Path | BinaryIO,
    size: tuple[int, int] = (200, 200),
    output_path: str | Path | None = None,
    fmt: str | None = None,
    quality: int = 85,
) -> str | BinaryIO | None:
    """生成等比缩略图（不超过 size 边界）。

    - output_path 为空时返回内存中的 BytesIO；
    - 指定 output_path 时保存并返回其字符串路径。
    """
    try:
        with open_image(source) as image:
            image.thumbnail(size, Image.LANCZOS)
            return _save(image, output_path, fmt, quality)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("生成缩略图失败：{}", exc)
        return None


def resize_image(
    source: str | Path | BinaryIO,
    width: int,
    height: int,
    output_path: str | Path | None = None,
    fmt: str | None = None,
    quality: int = 85,
    keep_ratio: bool = True,
) -> str | BinaryIO | None:
    """缩放图片。keep_ratio=True 为等比缩放（不超过给定边界），否则强制拉伸。"""
    try:
        with open_image(source) as image:
            if keep_ratio:
                image.thumbnail((width, height), Image.LANCZOS)
            else:
                image = image.resize((width, height), Image.LANCZOS)
            return _save(image, output_path, fmt, quality)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("缩放图片失败：{}", exc)
        return None


def convert_format(
    source: str | Path | BinaryIO,
    output_path: str | Path,
    fmt: str | None = None,
    quality: int = 85,
) -> str | None:
    """转换图片格式（默认按 output_path 的扩展名推断）。"""
    try:
        with open_image(source) as image:
            result = _save(image, output_path, fmt, quality)
            return str(result) if result is not None else None
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("转换图片格式失败：{}", exc)
        return None


def _ensure_rgb(image: Image.Image) -> Image.Image:
    """将带透明通道的图片合成到白色背景，得到可保存为 JPEG 的 RGB 图。"""
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _normalize_format(fmt: str | None, fallback: str) -> str:
    normalized = (fmt or fallback).upper().lstrip(".")
    if normalized == "JPG":
        normalized = "JPEG"
    return normalized


def _save(
    image: Image.Image,
    output_path: str | Path | None,
    fmt: str | None,
    quality: int,
) -> str | BinaryIO:
    """统一保存逻辑：无 output_path 返回 BytesIO，有则写文件并返回路径。"""
    if output_path is None:
        save_fmt = _normalize_format(fmt, image.format or "PNG")
        target = _ensure_rgb(image) if save_fmt in _RGB_REQUIRED_FORMATS else image
        buffer = io.BytesIO()
        target.save(buffer, format=save_fmt, quality=quality)
        buffer.seek(0)
        return buffer

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_fmt = _normalize_format(fmt, output_path.suffix or "PNG")
    target = _ensure_rgb(image) if save_fmt in _RGB_REQUIRED_FORMATS else image
    save_kwargs: dict = {"format": save_fmt}
    if save_fmt in _RGB_REQUIRED_FORMATS or save_fmt == "WEBP":
        save_kwargs["quality"] = quality
    target.save(output_path, **save_kwargs)
    return str(output_path)
