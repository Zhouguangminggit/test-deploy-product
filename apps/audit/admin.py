"""操作日志 Admin 配置。

仅 Django 自带后台管理可见（admin 默认要求 staff 登录）。
日志为只读数据：禁止在后台新增与修改，保留删除以便清理。
"""

from django.contrib import admin

from .models import OperationLog


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    """操作日志后台：只读列表 + 详情。"""

    list_display = ("created_at", "username", "action", "module", "object_repr", "ip_address")
    list_filter = ("action", "module", "created_at")
    search_fields = ("username", "object_repr", "message", "ip_address", "request_id")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    readonly_fields = (
        "user",
        "username",
        "action",
        "module",
        "object_repr",
        "message",
        "ip_address",
        "user_agent",
        "request_id",
        "created_at",
    )

    def has_add_permission(self, request):  # noqa: ANN001
        """日志由系统写入，后台禁止手动新增。"""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        """日志不可修改；返回 False 后详情页字段全部只读。"""
        return False
