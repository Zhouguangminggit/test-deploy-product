"""项目级路由入口。

- /admin/：Django 后台
- /healthz/：轻量健康检查端点（供部署探针 / 负载均衡使用）
- handler403/404/500：统一渲染 templates/errors/ 下的自定义错误页
  （仅在 DEBUG=False 时生效；开发环境可通过测试或临时关闭 DEBUG 预览）
"""

import re

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.urls import path, re_path
from django.views.static import serve


def healthz(request: HttpRequest) -> JsonResponse:
    """健康检查：返回服务存活状态。"""
    return JsonResponse({"status": "ok"})


def handler403(request: HttpRequest, exception=None):
    """403 禁止访问。"""
    return render(request, "errors/403.html", status=403)


def handler404(request: HttpRequest, exception=None):
    """404 页面不存在。"""
    return render(request, "errors/404.html", status=404)


def handler500(request: HttpRequest):
    """500 服务器内部错误。"""
    return render(request, "errors/500.html", status=500)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
]

# 开发环境由 Django 提供静态与媒体文件（dev 配置 DEBUG=False 用于预览错误页，
# 故额外按 settings 模块判断）；静态文件直接取源码目录，无需 collectstatic。
# 注意：不能用 django.conf.urls.static.static()，其内部以 settings.DEBUG 为开关，
# DEBUG=False 时返回空列表；此处直接用 serve 视图显式挂载。生产环境由 Nginx 提供。
if settings.DEBUG or settings.SETTINGS_MODULE == "config.settings.dev":
    urlpatterns += [
        re_path(
            rf"^{re.escape(settings.STATIC_URL.lstrip('/'))}(?P<path>.*)$",
            serve,
            {"document_root": settings.STATICFILES_DIRS[0]},
        ),
        re_path(
            rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
