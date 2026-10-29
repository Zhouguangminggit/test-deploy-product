"""seedkit 枚举定义。

触发方式、运行状态、日志级别统一在此登记，供模型 choices 与服务层复用，
保证中台与业务系统对同一状态机口径一致。
"""

from django.db import models


class SeedTrigger(models.TextChoices):
    """初始化触发方式。"""

    PLATFORM = "platform", "中台触发"
    LOCAL = "local", "本地脚本"
    SYNC = "sync", "同步执行"


class SeedRunStatus(models.TextChoices):
    """初始化运行状态机。"""

    PENDING = "pending", "待执行"
    RUNNING = "running", "执行中"
    SUCCESS = "success", "成功"
    PARTIAL = "partial", "部分成功"
    FAILED = "failed", "失败"


class SeedLogLevel(models.TextChoices):
    """运行日志级别（映射 loguru 同名方法）。"""

    INFO = "info", "信息"
    WARNING = "warning", "警告"
    ERROR = "error", "错误"
