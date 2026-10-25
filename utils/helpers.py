"""通用辅助函数。

与具体业务无关的纯函数集合：请求信息解析、字典合并、命名转换、
分块、字符串截断等。均为无副作用或副作用可控的工具函数。
"""

import itertools
import re
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

_CAMEL_TO_SNAKE_RE1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_TO_SNAKE_RE2 = re.compile(r"([a-z0-9])([A-Z])")


def get_client_ip(request: Any) -> str:
    """解析客户端真实 IP（兼容 Nginx 等反向代理的 X-Forwarded-For）。"""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        # X-Forwarded-For 可能是 "client, proxy1, proxy2"，取第一个
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """递归合并两个字典：override 覆盖 base，返回全新字典，不修改入参。"""
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def chunks(iterable: Iterable, size: int) -> Iterator[list]:
    """将可迭代对象按固定大小分块，最后一块可能不足 size。"""
    if size <= 0:
        raise ValueError("size 必须为正整数")
    iterator = iter(iterable)
    while True:
        chunk = list(itertools.islice(iterator, size))
        if not chunk:
            return
        yield chunk


def camel_to_snake(name: str) -> str:
    """驼峰转下划线：userName -> user_name。"""
    intermediate = _CAMEL_TO_SNAKE_RE1.sub(r"\1_\2", name or "")
    return _CAMEL_TO_SNAKE_RE2.sub(r"\1_\2", intermediate).lower()


def snake_to_camel(name: str, upper_first: bool = False) -> str:
    """下划线转驼峰：user_name -> userName（upper_first=True 时 -> UserName）。"""
    head, *rest = (name or "").split("_")
    if upper_first:
        head = head.capitalize()
    return head + "".join(word.capitalize() for word in rest)


def truncate(text: str, length: int, suffix: str = "...") -> str:
    """按最大长度截断字符串并追加后缀（后缀长度计入总长度）。"""
    text = text or ""
    if length <= 0:
        return ""
    if len(text) <= length:
        return text
    keep = max(0, length - len(suffix))
    return text[:keep] + suffix


def safe_int(value: Any, default: int = 0) -> int:
    """尽力将任意值转换为 int，失败返回默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
