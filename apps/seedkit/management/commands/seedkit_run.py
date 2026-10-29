"""触发业务数据初始化。

本地：``make seed-data`` → ``seedkit_run --trigger local --sync``（直接同步执行）。
线上：中台经 SSH 执行 ``seedkit_run``（默认异步），命令创建运行记录并投递 Celery 任务后
立即返回，stdout 输出单行 JSON（含 run_id / task_id），中台据此轮询 seedkit_status。

stdout 只输出 JSON，过程日志走 loguru（stderr）与 SeedRunLog（落库），互不干扰，
便于中台直接解析。失败以非零退出码返回，供 CI / 中台判断。
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.seedkit.enums import SeedRunStatus, SeedTrigger
from apps.seedkit.services import create_run, execute_run
from apps.seedkit.tasks import run_seedkit


class Command(BaseCommand):
    help = "触发业务数据初始化（本地 --sync 同步执行；线上默认异步投递 Celery）"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--module",
            action="append",
            default=[],
            metavar="NAME",
            help="仅初始化指定模块，可重复传入；缺省执行 YAML 中声明的全部模块",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="强制重填：先按声明逆序清空相关模型，再重新写入",
        )
        parser.add_argument(
            "--trigger",
            choices=[choice.value for choice in SeedTrigger],
            default=SeedTrigger.PLATFORM,
            help="触发方式标记（默认 platform）",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="同步执行（本地 / 调试用），不投递 Celery",
        )

    def handle(self, *args, **options) -> None:
        modules = options["module"] or []
        sync = options["sync"]
        trigger = SeedTrigger.SYNC if sync else options["trigger"]

        run = create_run(modules=modules, refresh=options["refresh"], trigger=trigger)

        if sync:
            execute_run(run)
            self._emit(
                {
                    "run_id": run.pk,
                    "status": run.status,
                    "created": run.created_count,
                    "skipped": run.skipped_count,
                    "images": run.image_count,
                    "error": run.error_message or None,
                }
            )
            if run.status == SeedRunStatus.FAILED:
                raise CommandError("数据初始化失败，详见运行日志")
            return

        try:
            async_result = run_seedkit.delay(run.pk)
        except Exception as exc:  # noqa: BLE001 - broker 不可达等投递异常，落库并以非零码返回
            run.status = SeedRunStatus.FAILED
            run.error_message = f"任务投递失败：{exc}"
            run.save(update_fields=["status", "error_message"])
            self._emit({"run_id": run.pk, "status": run.status, "error": run.error_message})
            raise CommandError(run.error_message) from exc

        run.celery_task_id = async_result.id
        run.save(update_fields=["celery_task_id"])
        self._emit({"run_id": run.pk, "task_id": async_result.id, "status": run.status})

    def _emit(self, payload: dict) -> None:
        """向 stdout 输出单行 JSON（中台解析入口）。"""
        self.stdout.write(json.dumps(payload, ensure_ascii=False))
