"""操作日志查询逻辑（selectors）。

供后台管理或后续统计功能使用；本模块不暴露前台视图。
"""

from django.db.models import QuerySet

from .models import OperationLog


def recent_logs(limit: int = 100) -> QuerySet[OperationLog]:
    """最近若干条操作日志。"""
    return OperationLog.objects.select_related("user")[:limit]


def filter_logs(
    *,
    user=None,
    action: str | None = None,
    module: str | None = None,
) -> QuerySet[OperationLog]:
    """按用户 / 动作 / 模块组合过滤操作日志。"""
    qs = OperationLog.objects.select_related("user")
    if user is not None:
        qs = qs.filter(user=user)
    if action:
        qs = qs.filter(action=action)
    if module:
        qs = qs.filter(module=module)
    return qs
