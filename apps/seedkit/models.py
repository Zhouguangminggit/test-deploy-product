"""数据初始化运行记录模型。

SeedRun 记录一次初始化运行（触发方式 / 目标模块 / 状态 / 统计 / 时间），
SeedRunLog 记录运行过程中的逐条日志。二者共同构成「可追溯」的核心：
既落库供业务系统后台查看，也通过 seedkit_status 命令暴露给中台轮询。
"""

from django.db import models

from .enums import SeedLogLevel, SeedRunStatus, SeedTrigger


class SeedRun(models.Model):
    """一次数据初始化运行。"""

    trigger = models.CharField(
        "触发方式",
        max_length=16,
        choices=SeedTrigger.choices,
        default=SeedTrigger.PLATFORM,
    )
    # 目标模块名列表；空列表表示执行 YAML 中声明的全部模块
    modules = models.JSONField("目标模块", default=list, blank=True)
    refresh = models.BooleanField("强制重填", default=False)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=SeedRunStatus.choices,
        default=SeedRunStatus.PENDING,
        db_index=True,
    )
    celery_task_id = models.CharField("Celery 任务 ID", max_length=64, blank=True)
    created_count = models.PositiveIntegerField("新增记录", default=0)
    skipped_count = models.PositiveIntegerField("跳过记录", default=0)
    image_count = models.PositiveIntegerField("下载图片", default=0)
    error_message = models.TextField("错误信息", blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "数据初始化记录"
        verbose_name_plural = "数据初始化记录"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.get_trigger_display()} {self.get_status_display()}"


class SeedRunLog(models.Model):
    """初始化运行的单条日志（双写：落库 + loguru）。"""

    run = models.ForeignKey(
        SeedRun,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="初始化记录",
    )
    level = models.CharField(
        "级别",
        max_length=16,
        choices=SeedLogLevel.choices,
        default=SeedLogLevel.INFO,
    )
    message = models.CharField("日志", max_length=512)
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "初始化日志"
        verbose_name_plural = "初始化日志"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"[{self.get_level_display()}] {self.message}"
