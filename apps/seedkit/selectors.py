"""数据初始化查询逻辑（selectors）。

供 seedkit_status 命令与后台管理复用；只读查询，不含副作用。
"""

from __future__ import annotations

from django.db.models import QuerySet

from .models import SeedRun, SeedRunLog


def get_run(run_id: int) -> SeedRun | None:
    """按主键取运行记录。"""
    return SeedRun.objects.filter(pk=run_id).first()


def latest_run() -> SeedRun | None:
    """最近一次运行记录。"""
    return SeedRun.objects.order_by("-created_at", "-pk").first()


def list_runs(limit: int = 50) -> QuerySet[SeedRun]:
    """最近若干次运行记录。"""
    return SeedRun.objects.order_by("-created_at", "-pk")[:limit]


def run_logs(run: SeedRun, *, tail: int | None = None) -> QuerySet[SeedRunLog]:
    """某次运行的日志（按写入顺序）；tail 指定时只取最后 N 条。"""
    qs = run.logs.order_by("id")
    if tail is not None and tail > 0:
        ids = list(qs.values_list("id", flat=True))[-tail:]
        qs = qs.filter(id__in=ids)
    return qs
