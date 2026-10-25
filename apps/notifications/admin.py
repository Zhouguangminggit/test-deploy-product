"""消息通知 Admin 配置。

管理员可在此撰写并发送消息：
- 定向消息：在表单中勾选收件用户（收件人为手动指定的中间表，
  不能用 filter_horizontal，改用 ModelMultipleChoiceField + save_m2m 写入）；
- 全站公告：选中消息后执行「发布为全站公告」动作，展开给所有激活用户。
收件记录以只读方式提供，便于查看送达 / 已读情况。
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model

from .models import Message, MessageAudience, MessageRecipient

User = get_user_model()


class MessageAdminForm(forms.ModelForm):
    """消息表单：收件人用多选控件直接指定（写 MessageRecipient）。"""

    recipient_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        label="收件人",
        widget=forms.SelectMultiple(attrs={"class": "vselectmultiv2", "size": "10"}),
        help_text="选择定向消息的收件用户；全站公告请用列表页动作。",
    )

    class Meta:
        model = Message
        # recipients 是手动指定中间表的 M2M，不直接编辑，统一走 recipient_users
        exclude = ("recipients",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["recipient_users"].initial = list(
                self.instance.recipient_set.filter(deleted=False).values_list("user", flat=True)
            )

    def save(self, commit=True):
        message = super().save(commit)
        self._pending_recipients = list(self.cleaned_data["recipient_users"])
        return message

    def save_m2m(self):
        """同步收件记录：新增勾选的用户，移除已取消勾选的用户。"""
        selected = list(getattr(self, "_pending_recipients", []))
        for user in selected:
            MessageRecipient.objects.get_or_create(message=self.instance, user=user)
        self.instance.recipient_set.exclude(user__in=selected).delete()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """消息后台。"""

    form = MessageAdminForm
    list_display = ("title", "audience", "level", "created_by", "recipient_count", "created_at")
    list_filter = ("audience", "level", "created_at")
    search_fields = ("title", "content")
    readonly_fields = ("created_at",)
    actions = ["publish_as_announcement"]

    def get_changeform_initial_data(self, request):  # noqa: ANN001
        """新建时默认发起人为当前管理员。"""
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("created_by", request.user.pk)
        return initial

    @admin.display(description="收件人数")
    def recipient_count(self, obj: Message) -> int:
        return obj.recipient_set.count()

    @admin.action(description="发布为全站公告（发送给所有激活用户）")
    def publish_as_announcement(self, request, queryset):
        """将所选消息展开为全体激活用户的收件记录。"""
        users = User.objects.filter(is_active=True)
        total = 0
        for message_obj in queryset:
            message_obj.audience = MessageAudience.ANNOUNCEMENT
            message_obj.save(update_fields=["audience"])
            created = 0
            for user in users.iterator():
                _, was_created = MessageRecipient.objects.get_or_create(
                    message=message_obj, user=user
                )
                created += int(was_created)
            total += created
        self.message_user(request, f"公告已发布，新增 {total} 条收件记录", messages.SUCCESS)


@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    """收件记录后台（只读查看）。"""

    list_display = ("message", "user", "is_read", "deleted", "created_at")
    list_filter = ("is_read", "deleted", "created_at")
    search_fields = ("message__title", "user__username")
    readonly_fields = ("message", "user", "is_read", "read_at", "deleted", "created_at")

    def has_add_permission(self, request):  # noqa: ANN001
        """收件记录由系统生成，后台不手动新增。"""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        """收件记录不可修改。"""
        return False
