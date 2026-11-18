"""消息通知模块应用配置。"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """消息通知应用。"""

    name = "apps.notifications"
    label = "notifications"
    verbose_name = "消息通知"
