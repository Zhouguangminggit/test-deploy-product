"""Celery 应用装配（项目唯一 Celery 入口）。

- broker 与定时任务调度：Redis + django-celery-beat（DatabaseScheduler，Admin 动态管理）；
- 任务结果：django-celery-results 落库（CELERY_RESULT_BACKEND = "django-db"，Admin 可查）；
- 各业务 app 的任务文件为 ``apps/<module>/tasks.py``，由 autodiscover_tasks 自动发现。

启动方式见 Makefile（make worker / make beat）与 SOP 文档 docs/README.md。
"""

import os

from celery import Celery
from celery.signals import task_failure
from django.apps import apps

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("django_scaffold")
# settings 中以 CELERY_ 前缀的键作为 Celery 配置来源（见 config/settings/base.py）
app.config_from_object("django.conf:settings", namespace="CELERY")
# 扫描所有已注册 app 下的 tasks.py（apps.accounts.tasks、apps.orders.tasks 等）；
# 延迟取值：worker 启动时 Django 已完成初始化，此时读 settings 安全
app.autodiscover_tasks(lambda: [c.name for c in apps.get_app_configs()])


@task_failure.connect
def _log_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """任务失败统一写入 Loguru（项目日志出口，见 utils/log.py）。"""
    from loguru import logger

    logger.error(
        "Celery 任务失败：task={} id={} 原因={}", sender and sender.name, task_id, exception
    )
