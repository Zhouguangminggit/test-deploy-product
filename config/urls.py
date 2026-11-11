"""项目级路由入口。

- /admin/：Django 后台
- /healthz/：轻量健康检查端点（供部署探针 / 负载均衡使用）
- handler403/404/500：统一渲染 templates/errors/ 下的自定义错误页
  （仅在 DEBUG=False 时生效；开发环境可通过测试或临时关闭 DEBUG 预览）
"""

import re

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.urls import include, path, re_path
from django.views.static import serve

from utils.admin_dashboard import dashboard


def home(request: HttpRequest):
    """前台首页（占位，展示基座与后续业务模块入口）。"""
    return render(request, "home.html")


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


admin.site.site_header = settings.SITE_NAME
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = "首页"
if settings.ADMIN_UI == "simpleui":
    admin.site.index_template = "admin/simpleui_index.html"
    admin.site.login_template = "admin/simpleui_login.html"

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("files/", include("apps.files.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("healthz/", healthz, name="healthz"),
    path("license/", include("apps.licensing.urls")),
]

if settings.ADMIN_UI == "simpleui":
    urlpatterns.insert(
        1, path("admin/dashboard/", admin.site.admin_view(dashboard), name="admin-dashboard")
    )

# 静态与媒体文件：
# - 开发环境（dev 配置 DEBUG=False 用于预览错误页，故额外按 settings 模块判断）由 Django
#   提供静态文件；生产环境不部署 Nginx，静态文件由 WhiteNoise 中间件直接提供 collectstatic 产物。
# - 静态：必须走 django.contrib.staticfiles.views.serve（基于 finders），
#   才能同时命中项目 static/ 与 Django admin 等第三方 app 位于 site-packages 的
#   静态资源；若用 django.views.static.serve(仅 STATICFILES_DIRS[0]) 会导致
#   admin 的 CSS/JS 404、后台退化为无样式裸页。insecure=True 以便 DEBUG=False 时仍可取。
if settings.DEBUG or settings.SETTINGS_MODULE == "config.settings.dev":
    urlpatterns += [
        re_path(
            rf"^{re.escape(settings.STATIC_URL.lstrip('/'))}(?P<path>.*)$",
            staticfiles_serve,
            {"insecure": True},
        ),
    ]

# 媒体文件：用户上传文件不在 staticfiles 索引内，任何环境均由应用从 MEDIA_ROOT 返回。
urlpatterns += [
    re_path(
        rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
