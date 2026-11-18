"""通用校验器。

校验失败统一抛出 django.core.exceptions.ValidationError，
可直接用于 Django Form / Model 字段校验或手动调用。
"""

import re

from django.core.exceptions import ValidationError

from .constants import MAX_UPLOAD_SIZE
from .file_helpers import get_extension, human_readable_size, is_extension_allowed
from .security import password_meets_policy

# 中国大陆手机号
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
# 用户名：3-32 位字母、数字、下划线或短横线
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")


def validate_phone(value: str) -> str:
    """校验中国大陆手机号，返回清洗后的值。"""
    cleaned = (value or "").strip()
    if not PHONE_RE.match(cleaned):
        raise ValidationError("请输入有效的中国大陆手机号")
    return cleaned


def validate_username(value: str) -> str:
    """校验用户名格式，返回清洗后的值。"""
    cleaned = (value or "").strip()
    if not USERNAME_RE.match(cleaned):
        raise ValidationError("用户名需为 3-32 位字母、数字、下划线或短横线")
    return cleaned


def validate_password_strength(value: str, min_length: int = 8) -> str:
    """校验密码强度（长度、字母、数字）。"""
    ok, errors = password_meets_policy(value or "", min_length)
    if not ok:
        raise ValidationError("；".join(errors))
    return value


def validate_file_size(file_obj, max_bytes: int = MAX_UPLOAD_SIZE) -> None:
    """校验上传文件大小；file_obj 需具备 size 属性（如 UploadedFile）。"""
    size = getattr(file_obj, "size", None)
    if size is None:
        return
    if size > max_bytes:
        raise ValidationError(f"文件大小不能超过 {human_readable_size(max_bytes)}")


def validate_file_extension(filename: str, allowed: set[str]) -> str:
    """校验文件扩展名是否在白名单内，返回文件名。"""
    if not is_extension_allowed(filename, allowed):
        raise ValidationError(f"不支持的文件类型：{get_extension(filename) or '未知'}")
    return filename
