"""SimpleUI 的后台模块数据概览。"""

from django.contrib import admin
from django.http import HttpRequest
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_safe


@require_safe
@xframe_options_sameorigin
def dashboard(request: HttpRequest):
    modules = []
    for app in admin.site.get_app_list(request):
        counts = []
        for item in app["models"]:
            if not item["admin_url"]:
                continue
            model_admin = admin.site.get_model_admin(item["model"])
            if not model_admin.has_view_or_change_permission(request):
                continue
            counts.append(
                {
                    "name": item["name"],
                    "url": item["admin_url"],
                    "count": model_admin.get_queryset(request)
                    .order_by()
                    .values("pk")
                    .distinct()
                    .count(),
                }
            )
        if counts:
            modules.append(
                {
                    "name": app["name"],
                    "models": counts,
                    "total": sum(item["count"] for item in counts),
                }
            )
    return render(
        request,
        "admin/module_dashboard.html",
        {
            "modules": modules,
            "summary": [{"name": module["name"], "value": module["total"]} for module in modules],
        },
    )
