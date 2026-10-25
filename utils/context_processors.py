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
