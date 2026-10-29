"""数据初始化 Admin 配置。

仅 Django 后台可见（admin 默认要求 staff 登录）：只读查看运行记录与逐条日志，
不提供后台触发（触发统一走 seedkit_run 命令 / 中台 SSH）。日志内联展示便于排查。
"""

from django.contrib import admin

from utils.admin_theme import ModelAdmin

from .models import SeedRun, SeedRunLog


class SeedRunLogInline(admin.TabularInline):
    """运行日志内联（只读）。"""

    model = SeedRunLog
    extra = 0
    fields = ("level", "message", "created_at")
    readonly_fields = ("level", "message", "created_at")
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):  # noqa: ANN001
        return False


@admin.register(SeedRun)
class SeedRunAdmin(ModelAdmin):
    """数据初始化记录后台：只读列表 + 日志内联。"""

    list_display = (
        "id",
        "status",
        "trigger",
        "refresh",
        "created_count",
        "skipped_count",
        "image_count",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "trigger", "refresh", "created_at")
    search_fields = ("celery_task_id", "error_message")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    inlines = (SeedRunLogInline,)

    readonly_fields = (
        "trigger",
        "modules",
        "refresh",
        "status",
        "celery_task_id",
        "created_count",
        "skipped_count",
        "image_count",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
    )

    def has_add_permission(self, request):  # noqa: ANN001
        """运行记录由命令写入，后台禁止手动新增。"""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        """运行记录不可修改；返回 False 后详情页字段全部只读。"""
        return False


@admin.register(SeedRunLog)
class SeedRunLogAdmin(ModelAdmin):
    """初始化日志后台：只读列表，便于跨运行检索。"""

    list_display = ("id", "run", "level", "message", "created_at")
    list_filter = ("level", "created_at")
    search_fields = ("message",)
    ordering = ("-created_at",)

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False
