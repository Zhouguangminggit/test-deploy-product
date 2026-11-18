"""消息通知模型。

采用「消息 + 收件记录」结构，统一支持三类消息：
- 定向消息（DIRECTED）：发给指定用户；
- 全站公告（ANNOUNCEMENT）：发布时展开为全体用户的收件记录；
- 事件自动通知（SYSTEM）：业务节点自动生成（如注册欢迎）。

每个用户对其收件记录独立维护已读 / 删除状态（MessageRecipient），
未读数、列表、详情均基于该表查询，逻辑简单直观，便于新手理解。
"""

from django.conf import settings
from django.db import models


class MessageLevel(models.TextChoices):
    """消息级别，映射前台提示样式。"""

    INFO = "info", "通知"
    SUCCESS = "success", "成功"
    WARNING = "warning", "警告"
    ERROR = "error", "错误"


class MessageAudience(models.TextChoices):
    """消息受众类型。"""

    DIRECTED = "directed", "定向"
    ANNOUNCEMENT = "announcement", "全站公告"
    SYSTEM = "system", "系统事件"


class Message(models.Model):
    """消息主体。"""

    title = models.CharField("标题", max_length=200)
    content = models.TextField("正文")
    level = models.CharField(
        "级别",
        max_length=16,
        choices=MessageLevel.choices,
        default=MessageLevel.INFO,
    )
    audience = models.CharField(
        "受众",
        max_length=16,
        choices=MessageAudience.choices,
        default=MessageAudience.DIRECTED,
    )
    # 通过收件记录表建立的用户多对多关系；定向消息可由后台直接勾选收件用户
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="MessageRecipient",
        through_fields=("message", "user"),
        related_name="received_messages",
        blank=True,
        verbose_name="收件人",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
        verbose_name="发起人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "消息"
        verbose_name_plural = "消息"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class MessageRecipient(models.Model):
    """用户对某条消息的收件记录（承载已读 / 删除状态）。"""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="recipient_set", verbose_name="消息"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_recipients",
        verbose_name="用户",
    )
    is_read = models.BooleanField("已读", default=False)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)
    deleted = models.BooleanField("已删除", default=False)
    created_at = models.DateTimeField("送达时间", auto_now_add=True)

    class Meta:
        verbose_name = "收件记录"
        verbose_name_plural = "收件记录"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="uniq_message_user"),
        ]

    def __str__(self) -> str:
        state = "已读" if self.is_read else "未读"
        return f"{self.user_id} <- {self.message_id} ({state})"
