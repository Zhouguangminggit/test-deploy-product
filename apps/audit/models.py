"""操作日志模型。

仅记录、仅在 Django 自带后台管理对管理员可见（不提供前台视图 / 路由）。
业务视图通过 @log_operation 装饰器显式埋点写入。
"""

from django.conf import settings
from django.db import models


class OperationAction(models.TextChoices):
    """操作动作类型。新增业务动作时在此登记，保证筛选与统计口径统一。"""

    LOGIN = "login", "登录"
    LOGOUT = "logout", "登出"
    REGISTER = "register", "注册"
    FILE_UPLOAD = "file_upload", "文件上传"
    FILE_DELETE = "file_delete", "文件删除"


class OperationLog(models.Model):
    """操作日志记录。"""

    # 关联用户；用户删除后置空，但保留 username 快照，确保日志可追溯
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_logs",
        verbose_name="操作用户",
    )
    username = models.CharField("用户名", max_length=150, blank=True)
    action = models.CharField("动作", max_length=32, choices=OperationAction.choices, db_index=True)
    module = models.CharField("所属模块", max_length=32, blank=True)
    object_repr = models.CharField("操作对象", max_length=255, blank=True)
    message = models.CharField("描述", max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("IP 地址", null=True, blank=True)
    user_agent = models.CharField("客户端", max_length=256, blank=True)
    request_id = models.CharField("请求 ID", max_length=32, blank=True, db_index=True)
    created_at = models.DateTimeField("操作时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        actor = self.username or "匿名"
        label = self.get_action_display()
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {actor} {label} {self.object_repr}".strip()
