"""消息通知业务逻辑（services）。

对外统一入口，供后台发送、其他模块事件触发（如注册欢迎）复用：
    from apps.notifications.services import notify_user, send_message, publish_announcement

所有发送最终落到 MessageRecipient 收件记录表，前台读写均以该表为准。
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from loguru import logger

from .models import Message, MessageAudience, MessageLevel, MessageRecipient

User = get_user_model()


def send_message(
    title: str,
    content: str,
    *,
    recipients,
    level: str = MessageLevel.INFO,
    audience: str = MessageAudience.DIRECTED,
    created_by=None,
) -> Message:
    """创建消息并生成收件记录（去重、忽略已存在）。"""
    users = list(recipients)
    with transaction.atomic():
        message = Message.objects.create(
            title=title,
            content=content,
            level=level,
            audience=audience,
            created_by=created_by,
        )
        rows = [MessageRecipient(message=message, user=user) for user in users]
        # ignore_conflicts 兼容唯一约束（同一用户重复收件）
        MessageRecipient.objects.bulk_create(rows, ignore_conflicts=True)
    logger.info("消息发送：id={} title={} 收件数={}", message.pk, title, len(rows))
    return message


def publish_announcement(
    title: str,
    content: str,
    *,
    created_by=None,
    level: str = MessageLevel.INFO,
) -> Message:
    """发布全站公告：为所有激活用户展开收件记录。"""
    users = User.objects.filter(is_active=True)
    return send_message(
        title,
        content,
        recipients=users,
        level=level,
        audience=MessageAudience.ANNOUNCEMENT,
        created_by=created_by,
    )


def notify_user(
    user,
    title: str,
    content: str,
    *,
    level: str = MessageLevel.INFO,
    audience: str = MessageAudience.SYSTEM,
    created_by=None,
) -> Message:
    """向单个用户发送系统事件通知。"""
    return send_message(
        title,
        content,
        recipients=[user],
        level=level,
        audience=audience,
        created_by=created_by,
    )


def mark_read(recipient: MessageRecipient) -> None:
    """标记单条收件记录为已读。"""
    if not recipient.is_read:
        recipient.is_read = True
        recipient.read_at = timezone.now()
        recipient.save(update_fields=["is_read", "read_at"])


def mark_all_read(user) -> int:
    """将用户全部未读消息标记为已读，返回更新条数。"""
    now = timezone.now()
    return MessageRecipient.objects.filter(user=user, is_read=False, deleted=False).update(
        is_read=True, read_at=now
    )


def delete_for_user(recipient: MessageRecipient) -> None:
    """软删除用户的一条收件记录（不影响其他用户与统计）。"""
    MessageRecipient.objects.filter(pk=recipient.pk).update(deleted=True)
