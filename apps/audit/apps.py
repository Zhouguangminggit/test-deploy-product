"""操作日志模块应用配置。"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    """操作日志应用。"""

    name = "apps.audit"
    label = "audit"
    verbose_name = "操作日志"
