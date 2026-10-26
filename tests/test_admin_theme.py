"""后台 UI 主题（unfold / simpleui）装配逻辑测试。

覆盖 utils/admin_theme.py 的纯函数装配（校验、app 列表、配置 dict 生成），
以及在当前 settings（dev 默认 unfold）下后台路由可解析、登录页可访问。
"""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from utils.admin_theme import (
    DEFAULT_ADMIN_UI,
    build_third_party_apps,
    build_theme_settings,
    validate_admin_ui,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("unfold", "unfold"),
        ("simpleui", "simpleui"),
        ("UNFOLD", "unfold"),        # 大小写不敏感
        ("  simpleui  ", "simpleui"),  # 去除首尾空白
        ("", DEFAULT_ADMIN_UI),       # 空值回退默认
        (None, DEFAULT_ADMIN_UI),     # 未设置回退默认
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
    settings_map = build_theme_settings(
        "unfold", site_name="测试站点", site_logo="", debug=True, static_url="static/"
    )
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
    # 未配置 logo 时不应出现 SITE_LOGO 键
    assert "SITE_LOGO" not in unfold


def test_unfold_theme_settings_with_logo():
    settings_map = build_theme_settings(
        "unfold", site_name="S", site_logo="images/logo.png", static_url="static/"
    )
    logo = settings_map["UNFOLD"]["SITE_LOGO"]
    assert logo["light"] == "static/images/logo.png"
    assert logo["dark"] == "static/images/logo.png"


def test_simpleui_theme_settings_content():
    settings_map = build_theme_settings("simpleui", site_name="测试站点", site_logo="")
    assert "UNFOLD" not in settings_map
    # 基础配置
    assert settings_map["SIMPLEUI_HOME_PAGE"] == "/"
    assert settings_map["SIMPLEUI_HOME_TITLE"] == "测试站点"
    # 净化项：关闭分析上报
    assert settings_map["SIMPLEUI_ANALYSIS"] is False


def test_admin_index_reverses_and_login_page_loads(client):
    """当前 dev settings（默认 unfold）下后台可正常路由与渲染登录页。"""
    url = reverse("admin:index")
    assert url == "/admin/"
    resp = client.get("/admin/login/")
    # 未登录访问后台首页会重定向到登录页，登录页本身应 200
    assert resp.status_code == 200
