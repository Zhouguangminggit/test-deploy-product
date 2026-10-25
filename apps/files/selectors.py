"""文件查询逻辑（selectors）。"""

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from .models import FileEntry

User = get_user_model()


def visible_files(user, category: str | None = None) -> QuerySet[FileEntry]:
    """普通用户仅见自己的文件；管理员（staff）可见全部。可按分类筛选。"""
    qs = FileEntry.objects.all()
    if not user.is_staff:
        qs = qs.filter(uploader=user)
    if category:
        qs = qs.filter(category=category)
    return qs.select_related("uploader")


def get_accessible_file(user, pk: int) -> FileEntry | None:
    """获取用户可访问的单个文件；无权访问返回 None。"""
    qs = visible_files(user) if user.is_staff else FileEntry.objects.filter(uploader=user)
    return qs.filter(pk=pk).first()
