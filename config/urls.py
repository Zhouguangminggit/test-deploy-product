"""项目级路由入口。

- /admin/：Django 后台
- /healthz/：轻量健康检查端点（供部署探针 / 负载均衡使用）
- handler403/404/500：统一渲染 templates/errors/ 下的自定义错误页
  （仅在 DEBUG=False 时生效；开发环境可通过测试或临时关闭 DEBUG 预览）
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.urls import path


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

# 开发环境由 Django 提供静态与媒体文件；生产环境由 Nginx 提供。
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
