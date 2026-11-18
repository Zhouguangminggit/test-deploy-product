"""文件名、文件大小等处理（通用能力，与 files 业务模块解耦）。"""

import os
import re
import uuid

# 允许中英文、数字、下划线、短横线与点，其余替换为下划线
_UNSAFE_FILENAME_RE = re.compile(r"[^\w.\-\u4e00-\u9fff]+")

_MAX_FILENAME_LENGTH = 200


def get_extension(filename: str) -> str:
    """返回小写扩展名（含点），无扩展名返回空串。"""
    return os.path.splitext(filename or "")[1].lower()


def sanitize_filename(filename: str, fallback: str = "file") -> str:
    """清洗文件名：剥离路径、移除不安全字符，防止目录穿越与非法字符。"""
    name = os.path.basename(filename or "").strip().replace("\x00", "")
    name = _UNSAFE_FILENAME_RE.sub("_", name).strip("._")
    if not name:
        name = fallback
    return name[:_MAX_FILENAME_LENGTH]


def human_readable_size(size_bytes: int | float | None, binary: bool = True) -> str:
    """将字节数转换为可读字符串，如 1536 -> '1.5 KiB'。"""
    if size_bytes is None:
        return ""
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return str(size_bytes)
    if size < 0:
        return "0 B"

    base = 1024 if binary else 1000
    units = ["B", "KiB", "MiB", "GiB", "TiB"] if binary else ["B", "KB", "MB", "GB", "TB"]

    index = 0
    while size >= base and index < len(units) - 1:
        size /= base
        index += 1
    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.1f} {units[index]}"


def generate_unique_filename(filename: str, prefix: str = "") -> str:
    """基于 UUID 生成唯一文件名，保留原扩展名，避免同名覆盖。"""
    ext = get_extension(sanitize_filename(filename))
    unique = uuid.uuid4().hex
    return f"{prefix}{unique}{ext}" if prefix else f"{unique}{ext}"


def is_extension_allowed(filename: str, allowed: set[str]) -> bool:
    """判断文件扩展名是否在白名单内（大小写不敏感）。"""
    allowed_lower = {ext.lower() for ext in allowed}
    return get_extension(filename) in allowed_lower
