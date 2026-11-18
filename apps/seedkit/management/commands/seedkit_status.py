"""查询数据初始化运行进度与日志（输出 JSON，供中台 SSH 轮询）。

用法：
    manage.py seedkit_status                     # 最近一次运行
    manage.py seedkit_status --run-id 12         # 指定运行
    manage.py seedkit_status --run-id 12 --tail 20
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.seedkit import selectors


class Command(BaseCommand):
    help = "查询数据初始化运行状态与日志（JSON 输出）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--run-id", type=int, default=None, help="运行记录主键；缺省取最近一次")
        parser.add_argument("--tail", type=int, default=50, help="返回最近 N 条日志（默认 50）")

    def handle(self, *args, **options) -> None:
        run_id = options["run_id"]
        run = selectors.get_run(run_id) if run_id else selectors.latest_run()
        if run is None:
            raise CommandError("未找到运行记录")

        logs = selectors.run_logs(run, tail=options["tail"])
        payload = {
            "run_id": run.pk,
            "status": run.status,
            "trigger": run.trigger,
            "refresh": run.refresh,
            "modules": run.modules,
            "celery_task_id": run.celery_task_id or None,
            "created": run.created_count,
            "skipped": run.skipped_count,
            "images": run.image_count,
            "error": run.error_message or None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "logs": [
                {"level": log.level, "message": log.message, "at": log.created_at.isoformat()}
                for log in logs
            ],
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False))
