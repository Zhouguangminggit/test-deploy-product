"""后台管理 UI 主题（django-unfold / django-simpleui）全局配置与装配入口。

本模块是整个脚手架切换 admin UI 主题的唯一出口，供 config/settings/base.py 调用：

- ``validate_admin_ui(value)``：校验 ADMIN_UI 取值（unfold / simpleui）；
- ``build_third_party_apps(admin_ui)``：返回需前置注册的主题 app 列表；
- ``build_theme_settings(...)``：返回需合并进全局 settings 的主题配置 dict；
- ``ModelAdmin`` / ``UserAdmin``：按当前主题解析的兼容基类，业务 admin.py 只需
  从这里导入即可「一套代码、双主题可用」。

设计要点：
- base.py 在 ``env.read_env()`` 之前就会 import 本模块，因此基类不能在模块加载时
  立即绑定；改用 PEP 562 模块级 ``__getattr__`` 延迟解析，等到各 app 的 admin.py
  被导入时（此时 settings 已就绪）再按 ``settings.ADMIN_UI`` 选择真正的基类。
- 具体的 UNFOLD / SIMPLEUI_* 键名以已安装版本的官方文档 / 源码为准。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

if TYPE_CHECKING:
    from django.http import HttpRequest

# ----------------------------- 主题常量 -----------------------------
DEFAULT_ADMIN_UI = "unfold"
# 支持的后台 UI 主题；非法取值启动即报错，避免拼写错误导致静默降级
ADMIN_UI_CHOICES = ("unfold", "simpleui")


def validate_admin_ui(value: str | None) -> str:
    """校验并规范化 ADMIN_UI 取值，空值回退默认主题。"""
    ui = (value or DEFAULT_ADMIN_UI).strip().lower()
    if ui not in ADMIN_UI_CHOICES:
        raise ImproperlyConfigured(
            f"ADMIN_UI={value!r} 不受支持，可选值：{', '.join(ADMIN_UI_CHOICES)}"
        )
    return ui


def build_third_party_apps(admin_ui: str) -> list[str]:
    """返回主题 app 列表；必须置于 django.contrib.admin 之前以覆盖其模板。

    - unfold：注册 ``unfold``，其 DefaultAppConfig.ready() 会把 admin.site 替换为
      UnfoldAdminSite，从而全站后台套用 unfold 样式；
    - simpleui：注册 ``simpleui``，它通过覆盖 admin 模板生效，无需替换 AdminSite。
    """
    ui = validate_admin_ui(admin_ui)
    if ui == "unfold":
        return ["unfold"]
    return ["simpleui"]


# ----------------------------- Unfold 配置 -----------------------------
def _unfold_sidebar_navigation() -> list[dict[str, Any]]:
    """按现有业务模块分组的侧边栏导航。

    每项 permission 直接传可调用对象（配置为 Python dict，无需序列化），
    由 unfold 在渲染时以 request 调用，实现按权限过滤菜单。
    """

    def _has_perm(perm: str):
        def _check(request: HttpRequest) -> bool:
            user = getattr(request, "user", None)
            return bool(user and user.is_authenticated and user.has_perm(perm))

        return _check

    return [
        {
            "items": [
                {
                    "title": "用户管理",
                    "icon": "people",
                    "link": reverse_lazy("admin:accounts_user_changelist"),
                    "permission": _has_perm("accounts.view_user"),
                },
                {
                    "title": "文件管理",
                    "icon": "folder",
                    "link": reverse_lazy("admin:files_fileentry_changelist"),
                    "permission": _has_perm("files.view_fileentry"),
                },
                {
                    "title": "操作日志",
                    "icon": "receipt_long",
                    "link": reverse_lazy("admin:audit_operationlog_changelist"),
                    "permission": _has_perm("audit.view_operationlog"),
                },
                {
                    "title": "消息通知",
                    "icon": "notifications",
                    "link": reverse_lazy("admin:notifications_message_changelist"),
                    "permission": _has_perm("notifications.view_message"),
                },
                {
                    "title": "定时任务",
                    "icon": "event",
                    "link": reverse_lazy("admin:django_celery_beat_periodictask_changelist"),
                    "permission": _has_perm("django_celery_beat.view_periodictask"),
                },
                {
                    "title": "任务结果",
                    "icon": "task",
                    "link": reverse_lazy("admin:django_celery_results_taskresult_changelist"),
                    "permission": _has_perm("django_celery_results.view_taskresult"),
                },
                {
                    "title": "数据初始化",
                    "icon": "database",
                    "link": reverse_lazy("admin:seedkit_seedrun_changelist"),
                    "permission": _has_perm("seedkit.view_seedrun"),
                },
            ],
        },
    ]


def environment_callback(request: HttpRequest) -> str:
    """unfold 顶部环境角标：dev 绿色、prod 红色，基于 DEBUG / SETTINGS_MODULE。"""
    from django.conf import settings
    from django.utils.html import format_html

    is_prod = settings.SETTINGS_MODULE.endswith("prod") or not settings.DEBUG
    label = "生产环境" if is_prod else "开发环境"
    color = "#dc2626" if is_prod else "#16a34a"
    return format_html(
        '<span style="background:{color};color:#fff;padding:2px 8px;'
        'border-radius:9999px;font-size:12px;">{label}</span>',
        color=color,
        label=label,
    )


def _build_unfold_settings(
    *, site_name: str, site_logo: str, debug: bool, static_url: str
) -> dict[str, Any]:
    """构造 UNFOLD 配置 dict（仅覆盖需要定制的键，其余走 unfold 默认值）。

    debug / static_url 由 base.py 以模块全局传入，避免在 settings 加载期
    访问 django.conf.settings 造成的懒加载递归。
    """
    # 站点 logo：配置了 SITE_LOGO 则拼接静态 URL 作为明暗两套，否则用 material 图标
    logo = None
    icon = "dashboard"
    if site_logo:
        logo_url = (
            site_logo
            if site_logo.startswith(("http://", "https://", "/"))
            else f"{static_url}{site_logo}"
        )
        logo = {"light": logo_url, "dark": logo_url}

    config: dict[str, Any] = {
        # ---- 站点品牌 ----
        "SITE_TITLE": site_name,
        "SITE_HEADER": site_name,
        "SITE_SYMBOL": icon,
        "SITE_URL": "/",
        # ---- 顶部栏与扩展开关 ----
        "SHOW_HISTORY": True,
        "SHOW_VIEW_ON_SITE": True,
        "SHOW_SEARCH": True,
        "SHOW_SETTINGS": True,
        "ENVIRONMENT": "utils.admin_theme.environment_callback",
        # ---- 侧边栏导航分组 ----
        "SIDEBAR": {
            "show_search": True,
            "show_all_applications": True,
            "navigation": _unfold_sidebar_navigation(),
        },
        # ---- 登录页 ----
        "LOGIN": {
            "image": None,
            "redirect_after": "/",
        },
        # 允许深色/浅色主题切换
        "THEME_LOCK": False,
        # ---- 颜色主题：primary 主色调（dev 绿、prod 蓝）----
        "COLORS": {
            "primary": {
                "500": "22 163 74" if debug else "37 99 235",
                "600": "21 128 61" if debug else "29 78 216",
            }
        },
    }
    if logo:
        config["SITE_LOGO"] = logo
    return config


# ----------------------------- SimpleUI 配置 -----------------------------
def _build_simpleui_settings(*, site_name: str, site_logo: str) -> dict[str, Any]:
    """构造 SIMPLEUI_* 平铺配置（基础配置 + 净化项）。

    说明：当前 simpleui 版本已内置本地静态资源（无 CDN 依赖），无需 SIMPLEUI_STATIC_OFFLINE。
    """
    settings_map: dict[str, Any] = {
        # ---- 基础配置 ----
        "SIMPLEUI_HOME_PAGE": "/",  # 首页按钮跳转到站点前台首页
        "SIMPLEUI_HOME_TITLE": site_name,
        "SIMPLEUI_HOME_ICON": "fa fa-home",
        "SIMPLEUI_INDEX": "/",  # 登录后默认落地页
        "SIMPLEUI_DEFAULT_THEME": "admin.lte.css",
        "SIMPLEUI_LOGO": site_logo or "",
        # ---- 净化项：关闭上报分析与登录页粒子动画 ----
        "SIMPLEUI_ANALYSIS": False,
        "SIMPLEUI_LOGIN_PARTICLES": False,
        # 首页服务器信息 / 快捷操作面板开关
        "SIMPLEUI_HOME_INFO": False,
        "SIMPLEUI_HOME_QUICK": True,
    }
    return settings_map


def build_theme_settings(
    admin_ui: str,
    *,
    site_name: str,
    site_logo: str = "",
    debug: bool = False,
    static_url: str = "static/",
) -> dict[str, Any]:
    """按当前主题返回需合并进全局 settings 的配置 dict。"""
    ui = validate_admin_ui(admin_ui)
    if ui == "unfold":
        return {
            "UNFOLD": _build_unfold_settings(
                site_name=site_name,
                site_logo=site_logo,
                debug=debug,
                static_url=static_url,
            )
        }
    return _build_simpleui_settings(site_name=site_name, site_logo=site_logo)


# ----------------------------- 兼容基类（延迟解析） -----------------------------
def _resolve_admin_ui() -> str:
    """在 settings 就绪后解析当前主题；未就绪时回退默认值。"""
    try:
        from django.conf import settings

        if settings.configured:
            return validate_admin_ui(getattr(settings, "ADMIN_UI", DEFAULT_ADMIN_UI))
    except Exception:  # noqa: BLE001 - settings 尚未就绪时的兜底
        pass
    return DEFAULT_ADMIN_UI


def _resolve_base_class(name: str) -> Any:
    """按当前主题返回 ModelAdmin / UserAdmin 兼容基类。"""
    ui = _resolve_admin_ui()
    if ui == "unfold":
        from unfold.admin import ModelAdmin as UnfoldModelAdmin

        if name == "UserAdmin":
            # unfold 未提供 UserAdmin，复用原生 auth UserAdmin 即可正常渲染
            from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

            return DjangoUserAdmin
        return UnfoldModelAdmin

    from django.contrib.admin import ModelAdmin as DjangoModelAdmin

    if name == "UserAdmin":
        from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

        return DjangoUserAdmin
    return DjangoModelAdmin


def __getattr__(name: str) -> Any:
    """PEP 562 模块级延迟属性：按需解析 ModelAdmin / UserAdmin 基类。

    app 的 admin.py 在 django.setup() 之后导入本模块，此时 settings 已就绪，
    可据 ADMIN_UI 选择正确的基类，实现「一套 admin 代码、双主题可用」。
    """
    if name in ("ModelAdmin", "UserAdmin"):
        return _resolve_base_class(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
