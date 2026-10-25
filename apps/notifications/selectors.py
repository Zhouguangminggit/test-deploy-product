"""消息通知查询逻辑（selectors）。"""

from django.db.models import QuerySet

from .models import MessageRecipient


def inbox(user, *, only_unread: bool = False) -> QuerySet[MessageRecipient]:
    """用户收件箱（排除软删除），可选仅未读。"""
    qs = MessageRecipient.objects.filter(user=user, deleted=False).select_related("message", "user")
    if only_unread:
        qs = qs.filter(is_read=False)
    return qs.order_by("-created_at")


def get_for_user(user, pk: int) -> MessageRecipient | None:
    """获取属于该用户且未删除的收件记录；否则返回 None。"""
    return MessageRecipient.objects.filter(pk=pk, user=user, deleted=False).select_related("message").first()


def unread_count(user) -> int:
    """用户未读消息数。"""
    return MessageRecipient.objects.filter(user=user, is_read=False, deleted=False).count()
