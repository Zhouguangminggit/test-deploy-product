"""通用权限辅助函数与装饰器（不绑定具体业务模型）。

基于 Django 内置的 User / Group 体系提供通用判断；
更细粒度的角色 / 菜单权限在第二步 permissions 模块中实现。
"""

import functools
from collections.abc import Iterable

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest


def is_authenticated(user) -> bool:
    """是否已登录。"""
    return bool(user and user.is_authenticated)


def is_staff(user) -> bool:
    """是否为员工（可进入后台）。"""
    return bool(user and user.is_authenticated and user.is_staff)


def is_superuser(user) -> bool:
    """是否为超级管理员。"""
    return bool(user and user.is_authenticated and user.is_superuser)


def user_in_groups(user, group_names: Iterable[str]) -> bool:
    """判断用户是否属于给定用户组之一；超级管理员恒为 True。"""
    if not is_authenticated(user):
        return False
    if user.is_superuser:
        return True
    names = set(group_names)
    user_groups = set(user.groups.values_list("name", flat=True))
    return bool(names & user_groups)


def staff_required(view_func):
    """要求已登录且为员工，否则跳转登录页。"""
    return user_passes_test(is_staff)(view_func)


def group_required(*group_names: str):
    """要求已登录且属于指定用户组之一，否则抛出 403。"""

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            if not user_in_groups(request.user, group_names):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
