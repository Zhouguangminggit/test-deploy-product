"""用户账户 Admin 配置。"""

from django.contrib import admin
from django.utils.html import format_html

from utils.admin_theme import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """自定义用户后台：在内置基础上补充昵称、头像、手机号。"""

    list_display = ("avatar_thumb", "username", "nickname", "phone", "email", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "groups")
    search_fields = ("username", "nickname", "phone", "email")
    ordering = ("-date_joined",)

    # 在内置字段组后追加自定义字段
    fieldsets = BaseUserAdmin.fieldsets + (
        ("扩展信息", {"fields": ("nickname", "avatar", "phone")}),
    )

    @admin.display(description="头像")
    def avatar_thumb(self, obj: User) -> str:
        """列表页头像缩略图；无头像时显示占位符。"""
        if obj.avatar:
            return format_html('<img src="{}" style="height:32px;width:32px;border-radius:50%;" />', obj.avatar.url)
        return "—"
