"""Django 公共配置（所有环境共享）。

- 通过 django-environ 从项目根目录 .env 读取环境变量；
- 环境差异（DEBUG、数据库、安全项）在 dev.py / prod.py 中覆盖；
- 通用能力层 utils 作为本地应用注册，以支持 {% load common_tags %}。
"""

from pathlib import Path

import environ

from utils.log import build_logging_config

# 项目根目录：config/settings/base.py -> 上溯三级
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 初始化环境变量读取器（含默认值类型声明）
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    TIME_ZONE=(str, "Asia/Shanghai"),
    LANGUAGE_CODE=(str, "zh-hans"),
    SECURE_SSL_REDIRECT=(bool, False),
)
# 加载根目录 .env（存在才读取，不覆盖已有环境变量）
env.read_env(str(BASE_DIR / ".env"))

# ----------------------------- 安全与调试 -----------------------------
SECRET_KEY = env("SECRET_KEY", default="insecure-development-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ----------------------------- 应用注册 -----------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# 第三方应用（后续步骤按需追加，如 django 扩展库）
THIRD_PARTY_APPS: list[str] = []

# 项目本地应用：utils 提供 templatetags 等通用能力
LOCAL_APPS = [
    "utils",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ----------------------------- 中间件 -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "utils.middleware.RequestMetaMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ----------------------------- 模板 -----------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "utils.context_processors.site_info",
            ],
            # 全局内置模板标签，无需在每个模板 {% load %}
            "builtins": [
                "utils.templatetags.common_tags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ----------------------------- 数据库 -----------------------------
# 默认使用 SQLite（开发零配置）；生产环境在 prod.py 覆盖为 MySQL。
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ----------------------------- 密码校验 -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----------------------------- 国际化 -----------------------------
LANGUAGE_CODE = env("LANGUAGE_CODE")
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# ----------------------------- 站点信息 -----------------------------
# 由 utils.context_processors.site_info 注入模板，供页面头部/标题使用
SITE_NAME = env("SITE_NAME", default="Django Scaffold")
SITE_DESCRIPTION = env("SITE_DESCRIPTION", default="团队产品基座脚手架")

# ----------------------------- 静态与媒体文件 -----------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----------------------------- 主键与登录跳转 -----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 采用路径形式（而非命名 URL），避免第二步账号模块就绪前反解失败
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ----------------------------- 邮件 -----------------------------
# 默认输出到控制台；生产环境在 prod.py 按需切换为 SMTP。
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# ----------------------------- 安全（基线，可在 prod 加固）-----------------------------
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
X_FRAME_OPTIONS = "SAMEORIGIN"

# ----------------------------- 日志（Loguru）-----------------------------
# 统一后端日志出口为 Loguru：
# - LOG_LEVEL：控制台与文件 sink 共用的日志级别；
# - LOG_DIR：文件日志目录，留空表示仅输出到控制台（容器环境推荐留空，由采集系统收集 stderr）；
# - 实际的 Loguru 装配（sink / 格式 / 轮转 / request_id 注入）在 utils.apps.UtilsConfig.ready() 完成；
# - 此处 LOGGING 仅负责把标准库 logging（含 Django 内部 logger）导入 Loguru。
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_DIR = env("LOG_DIR", default="")
LOGGING = build_logging_config(LOG_LEVEL)
