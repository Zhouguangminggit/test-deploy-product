"""数据初始化 Celery 任务编排。

只做编排：接收主键等可序列化参数，核心执行逻辑在 services.execute_run_by_id。
中台经 SSH 触发 seedkit_run 命令投递本任务，worker 异步执行、结果与日志落库。
"""

from __future__ import annotations

from celery import shared_task

from .services import execute_run_by_id


@shared_task(name="apps.seedkit.run_seedkit")
def run_seedkit(run_id: int) -> int:
    """异步执行一次数据初始化，返回运行记录主键。"""
    run = execute_run_by_id(run_id)
    return run.pk
