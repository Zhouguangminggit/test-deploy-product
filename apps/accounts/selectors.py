"""用户账户查询逻辑（selectors）。

视图与 services 通过 selectors 获取用户，避免直接散 filter 查询，
便于后续统一加缓存或扩展查询条件。
"""

from django.contrib.auth import get_user_model

User = get_user_model()


def get_user_by_id(pk: int):
    """按主键获取用户，不存在返回 None。"""
    return User.objects.filter(pk=pk).first()


def get_user_by_username(username: str):
    """按用户名获取用户，不存在返回 None。"""
    return User.objects.filter(username=username).first()


def user_exists(username: str) -> bool:
    """用户名是否已存在。"""
    return User.objects.filter(username=username).exists()
