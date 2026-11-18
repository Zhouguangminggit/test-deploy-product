"""后台 UI 主题（unfold / simpleui）装配逻辑测试。

覆盖 utils/admin_theme.py 的纯函数装配（校验、app 列表、配置 dict 生成），
以及在当前 settings（dev 默认 unfold）下后台路由可解析、登录页可访问。
"""

import json

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import override

from utils.admin_theme import (
    DEFAULT_ADMIN_UI,
    build_theme_settings,
    build_third_party_apps,
    validate_admin_ui,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("unfold", "unfold"),
        ("simpleui", "simpleui"),
        ("UNFOLD", "unfold"),  # 大小写不敏感
        ("  simpleui  ", "simpleui"),  # 去除首尾空白
        ("", DEFAULT_ADMIN_UI),  # 空值回退默认
        (None, DEFAULT_ADMIN_UI),  # 未设置回退默认
    ],
)
def test_validate_admin_ui_ok(raw, expected):
    assert validate_admin_ui(raw) == expected


def test_validate_admin_ui_rejects_unknown():
    with pytest.raises(ImproperlyConfigured):
        validate_admin_ui("grappelli")


def test_build_third_party_apps_unfold():
    apps = build_third_party_apps("unfold")
    assert apps == ["unfold"]


def test_build_third_party_apps_simpleui():
    apps = build_third_party_apps("simpleui")
    assert apps == ["simpleui"]


def test_unfold_theme_settings_content():
    settings_map = build_theme_settings("unfold", site_name="测试站点", debug=True)
    assert "UNFOLD" in settings_map
    unfold = settings_map["UNFOLD"]
    # 站点品牌联动 SITE_NAME
    assert unfold["SITE_TITLE"] == "测试站点"
    assert unfold["SITE_HEADER"] == "测试站点"
    # 侧边栏导航分组存在且非空
    assert unfold["SIDEBAR"]["navigation"]
    # 顶部栏扩展开关
    assert unfold["SHOW_HISTORY"] is True
    assert unfold["SHOW_VIEW_ON_SITE"] is True
    # 颜色主题与登录页
    assert "primary" in unfold["COLORS"]
    assert unfold["LOGIN"]["redirect_after"] == "/"
    assert unfold["SITE_SYMBOL"] == "测"
    assert "SITE_LOGO" not in unfold


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("https://example.com/logo.svg", "https://example.com/logo.svg"),
        ("/media/logo.svg", "/media/logo.svg"),
        ("images/logo.svg", "/static/images/logo.svg"),
    ],
)
def test_frontend_and_admin_share_logo(client, admin_user, configured, expected):
    client.force_login(admin_user)
    with override_settings(SITE_LOGO=configured, SETTINGS_MODULE=settings.SETTINGS_MODULE):
        assert f'src="{expected}"' in client.get(reverse("home")).content.decode()
        index = client.get(reverse("admin:index"))
        assert f'src="{expected}"' in index.content.decode()
        assert settings.SITE_NAME in index.content.decode()


def test_simpleui_theme_settings_content():
    settings_map = build_theme_settings("simpleui", site_name="测试站点")
    assert "UNFOLD" not in settings_map
    # 基础配置
    assert settings_map["SIMPLEUI_INDEX"] == reverse("admin:index")
    assert settings_map["SIMPLEUI_HOME_TITLE"] == "首页"
    # 净化项：关闭分析上报
    assert settings_map["SIMPLEUI_ANALYSIS"] is False


def test_admin_index_reverses_and_login_page_loads(client):
    """当前 dev settings（默认 unfold）下后台可正常路由与渲染登录页。"""
    url = reverse("admin:index")
    assert url == "/admin/"
    resp = client.get("/admin/login/")
    # 未登录访问后台首页会重定向到登录页，登录页本身应 200
    assert resp.status_code == 200
    assert admin.site.index_title == "首页"
    assert settings.SITE_NAME in resp.content.decode()


@pytest.mark.django_db
@pytest.mark.skipif(settings.ADMIN_UI != "simpleui", reason="需要 ADMIN_UI=simpleui")
def test_simpleui_home_counts_only_visible_records(client, monkeypatch):
    url = reverse("admin-dashboard")
    assert client.get(url).status_code == 302

    user_model = get_user_model()
    staff = user_model.objects.create_user(username="dashboard-staff", is_staff=True)
    user_model.objects.create_user(username="another-user")
    client.force_login(staff)
    assert client.get(url).context["summary"] == []

    staff.user_permissions.add(
        Permission.objects.get(codename="view_user", content_type__app_label="accounts")
    )
    model_admin = admin.site.get_model_admin(user_model)
    monkeypatch.setattr(
        model_admin, "get_queryset", lambda request: user_model.objects.filter(pk=request.user.pk)
    )
    index = client.get(reverse("admin:index"))
    assert url in index.content.decode()
    assert settings.SITE_NAME in index.content.decode()
    assert "admin/simpleui-x/img/logo.png" not in index.content.decode()

    response = client.get(url)
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    assert response.context["summary"] == [{"name": "用户账户", "value": 1}]
    assert response.context["modules"][0]["models"][0]["url"] == reverse(
        "admin:accounts_user_changelist"
    )


@pytest.mark.skipif(settings.ADMIN_UI != "simpleui", reason="需要 ADMIN_UI=simpleui")
def test_simpleui_celery_results_menu_and_dashboard(admin_client):
    with override("zh-hans"):
        assert admin_client.get(reverse("admin:index")).status_code == 200
        menus = json.loads(admin_client.session["_menus"])
        results = next(menu for menu in menus if menu["name"] == "异步任务结果")
        assert results["icon"] == "fas fa-clipboard-check"
        assert {item["name"]: item["icon"] for item in results["models"]} == {
            "任务结果": "fas fa-list-check",
            "任务组结果": "fas fa-layer-group",
        }
        overview = admin_client.get(reverse("admin-dashboard"))
        assert any(item["name"] == "异步任务结果" for item in overview.context["summary"])
