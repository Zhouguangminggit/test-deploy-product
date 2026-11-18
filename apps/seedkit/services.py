"""数据初始化业务逻辑（services）。

对外统一入口：
    from apps.seedkit.services import create_run, execute_run, execute_run_by_id

- create_run：登记一次运行（SeedRun），供中台/本地命令投递 Celery 或同步执行；
- execute_run：加载 YAML、调用引擎逐模块填充、把过程日志双写 DB + loguru，
  并按结果流转状态机（success / partial / failed）；核心填充逻辑在 engine.py。

RunLogger 是「可追溯」的落点：每条日志既写 SeedRunLog（后台与 seedkit_status 可查），
又经 loguru 输出（业务系统日志文件可见）。
"""

from __future__ import annotations

from django.utils import timezone
from loguru import logger

from .engine import SeedRunPartial, SeedStats, run_config
from .enums import SeedLogLevel, SeedRunStatus, SeedTrigger
from .loader import SeedConfigError, load_config
from .models import SeedRun, SeedRunLog


class RunLogger:
    """运行日志器：双写 SeedRunLog（落库）与 loguru（业务日志）。"""

    def __init__(self, run: SeedRun) -> None:
        self.run = run

    def _write(self, level: str, message: str) -> None:
        SeedRunLog.objects.create(run=self.run, level=level, message=str(message)[:512])
        getattr(logger, level)("[seedkit] {}", message)

    def info(self, message: str) -> None:
        self._write(SeedLogLevel.INFO, message)

    def warning(self, message: str) -> None:
        self._write(SeedLogLevel.WARNING, message)

    def error(self, message: str) -> None:
        self._write(SeedLogLevel.ERROR, message)


def create_run(
    *,
    modules: list[str] | None = None,
    refresh: bool = False,
    trigger: str = SeedTrigger.PLATFORM,
) -> SeedRun:
    """创建一条待执行运行记录（不触发执行）。"""
    return SeedRun.objects.create(
        trigger=trigger,
        modules=list(modules or []),
        refresh=refresh,
        status=SeedRunStatus.PENDING,
    )


def _mark_running(run: SeedRun, log: RunLogger) -> bool:
    started_at = timezone.now()
    if not SeedRun.objects.filter(pk=run.pk, status=SeedRunStatus.PENDING).update(
        status=SeedRunStatus.RUNNING, started_at=started_at
    ):
        run.refresh_from_db()
        return False
    run.status = SeedRunStatus.RUNNING
    run.started_at = started_at
    log.info(
        f"开始初始化：trigger={run.trigger} modules={run.modules or '全部'} refresh={run.refresh}"
    )
    return True


def _finish(run: SeedRun, log: RunLogger, stats: SeedStats) -> SeedRun:
    run.created_count = stats.created
    run.skipped_count = stats.skipped
    run.image_count = stats.images
    run.status = SeedRunStatus.SUCCESS
    run.finished_at = timezone.now()
    run.error_message = ""
    run.save(
        update_fields=[
            "created_count",
            "skipped_count",
            "image_count",
            "status",
            "finished_at",
            "error_message",
        ]
    )
    log.info(f"初始化完成：新增 {stats.created}，跳过 {stats.skipped}，图片 {stats.images}")
    return run


def _fail(run: SeedRun, log: RunLogger, message: str) -> SeedRun:
    run.status = SeedRunStatus.FAILED
    run.error_message = message
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_message", "finished_at"])
    log.error(message)
    return run


def execute_run(run: SeedRun) -> SeedRun:
    """同步执行一次运行：加载配置 → 引擎填充 → 状态流转。异常不外泄，统一落到状态与日志。"""
    log = RunLogger(run)
    if not _mark_running(run, log):
        return run

    try:
        config = load_config()
    except SeedConfigError as exc:
        return _fail(run, log, f"配置校验失败：{exc}")

    try:
        stats = run_config(config, modules=run.modules or None, refresh=run.refresh, log=log)
    except SeedRunPartial as partial:
        run.created_count = partial.stats.created
        run.skipped_count = partial.stats.skipped
        run.image_count = partial.stats.images
        run.status = SeedRunStatus.PARTIAL
        run.error_message = f"失败模块：{', '.join(partial.failed_modules)}"
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "created_count",
                "skipped_count",
                "image_count",
                "status",
                "error_message",
                "finished_at",
            ]
        )
        log.warning(run.error_message)
        return run
    except SeedConfigError as exc:
        return _fail(run, log, f"种子执行失败：{exc}")
    except Exception as exc:  # noqa: BLE001 - 兜底：任何未预期异常都落 failed，不把栈抛给中台
        logger.exception("数据初始化运行 {} 失败", run.pk)
        return _fail(run, log, f"初始化异常：{exc}")

    return _finish(run, log, stats)


def execute_run_by_id(run_id: int) -> SeedRun:
    """按主键取运行记录并执行（Celery 任务入口）。"""
    run = SeedRun.objects.get(pk=run_id)
    return execute_run(run)
