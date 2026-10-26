"""文件管理 Admin 配置。"""

from django.contrib import admin

from utils.admin_theme import ModelAdmin
from utils.file_helpers import human_readable_size

from .models import FileEntry


@admin.register(FileEntry)
class FileEntryAdmin(ModelAdmin):
    """文件记录后台：只读展示，不提供在线编辑。"""

    list_display = ("original_name", "uploader", "category", "size_display", "uploaded_at")
    list_filter = ("category", "uploaded_at")
    search_fields = ("original_name", "uploader__username")
    date_hierarchy = "uploaded_at"
    readonly_fields = ("uploader", "original_name", "file", "category", "size", "content_type", "uploaded_at")

    def has_add_permission(self, request):  # noqa: ANN001
        """文件通过业务界面上传，后台禁止手动新增。"""
        return False

    @admin.display(description="大小")
    def size_display(self, obj: FileEntry) -> str:
        return human_readable_size(obj.size)
