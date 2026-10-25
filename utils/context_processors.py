"""模板全局上下文处理器。

在 settings.TEMPLATES 的 context_processors 中注册后，
所有模板无需显式传参即可获得这些变量。
"""

from django.conf import settings
from django.http import HttpRequest


def site_info(request: HttpRequest) -> dict:
    """注入站点信息与当前请求的 request-id。"""
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "Django Scaffold"),
        "SITE_DESCRIPTION": getattr(settings, "SITE_DESCRIPTION", "团队产品基座脚手架"),
        "SITE_LOGO": getattr(settings, "SITE_LOGO", ""),
        "REQUEST_ID": getattr(request, "request_id", ""),
    }


def notification_badge(request: HttpRequest) -> dict:
    """为已登录用户注入未读消息数，供导航栏全局角标使用。

    延迟导入 notifications，避免通用层与业务模块的循环依赖；
    未登录或模块未就绪时返回 0。
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"UNREAD_MESSAGE_COUNT": 0}
    try:
        from apps.notifications import selectors

        return {"UNREAD_MESSAGE_COUNT": selectors.unread_count(user)}
    except Exception:  # noqa: BLE001 - 角标不应影响页面渲染
        return {"UNREAD_MESSAGE_COUNT": 0}
