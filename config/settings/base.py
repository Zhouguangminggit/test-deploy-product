"""Django 公共配置（所有环境共享）。

- 通过 django-environ 从项目根目录 .env 读取环境变量；
- 环境差异（DEBUG、数据库、安全项）在 dev.py / prod.py 中覆盖；
- 通用能力层 utils 作为本地应用注册，以支持 {% load common_tags %}。
"""

from pathlib import Path

import environ

from utils.admin_theme import build_theme_settings, build_third_party_apps, validate_admin_ui
from utils.log import build_logging_config

# 项目根目录：config/settings/base.py -> 上溯三级
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 初始化环境变量读取器（含默认值类型声明）
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    TIME_ZONE=(str, "Asia/Shanghai"),
    LANGUAGE_CODE=(str, "zh-hans"),
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
# - django_celery_beat：周期任务存库，Admin 动态管理（DatabaseScheduler）；
# - django_celery_results：任务结果落库，Admin 可查执行记录。
THIRD_PARTY_APPS: list[str] = [
    "django_celery_beat",
    "django_celery_results",
]

# 项目本地应用：utils 提供 templatetags 等通用能力；accounts 用户账户；files 文件管理；audit 操作日志；notifications 消息通知；seedkit 数据初始化
LOCAL_APPS = [
    "utils",
    "apps.accounts",
    "apps.files",
    "apps.audit",
    "apps.notifications",
    "apps.seedkit",
]

ADMIN_UI = validate_admin_ui(env("ADMIN_UI", default="unfold"))
ADMIN_THEME_APPS = build_third_party_apps(ADMIN_UI)

INSTALLED_APPS = ADMIN_THEME_APPS + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# 自定义用户模型（accounts.User 继承 AbstractUser）。
# 必须在首次迁移前设置；label 为 "accounts"，故写 "accounts.User"。
AUTH_USER_MODEL = "accounts.User"

# ----------------------------- 中间件 -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # 生产环境由应用直接提供静态文件（无需独立 Nginx）
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "utils.context_processors.notification_badge",
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
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

# ----------------------------- 站点信息 -----------------------------
# 由 utils.context_processors.site_info 注入模板，供页面头部/标题使用
SITE_NAME = env("SITE_NAME", default="Django Scaffold")
SITE_DESCRIPTION = env("SITE_DESCRIPTION", default="团队产品基座脚手架")
# 前后台共用 logo；相对路径由静态资源存储解析，留空显示文字徽标
SITE_LOGO = env("SITE_LOGO", default="")

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

# ----------------------------- 异步任务（Celery + Redis）-----------------------------
# Redis 同时作为 broker 与定时任务发布通道；任务结果走 django-db 落库（Admin 可查）。
# 环境差异：dev 默认连团队共享开发 Redis（db1），prod 由环境变量注入云 Redis 内网地址。
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = "django-db"
# 关闭 Redis result key 缓存，减轻云 Redis 压力（结果以库表为准）
CELERY_RESULT_CACHE = None
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_TRACK_STARTED = True
# 单个 worker 进程不预取多条，避免长任务阻塞队列；每 50 个任务重启子进程防内存泄漏
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50

# ----------------------------- 日志（Loguru）-----------------------------
# 统一后端日志出口为 Loguru：
# - LOG_LEVEL：控制台与文件 sink 共用的日志级别；
# - LOG_DIR：文件日志目录，留空表示仅输出到控制台（容器环境推荐留空，由采集系统收集 stderr）；
# - 实际的 Loguru 装配（sink / 格式 / 轮转 / request_id 注入）在 utils.apps.UtilsConfig.ready() 完成；
# - 此处 LOGGING 仅负责把标准库 logging（含 Django 内部 logger）导入 Loguru。
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_DIR = env("LOG_DIR", default="")
LOGGING = build_logging_config(LOG_LEVEL)

# ----------------------------- seedkit 数据初始化 -----------------------------
# 统一 YAML 配置驱动业务数据初始化（详见 apps/seedkit）：
# - PIXABAY_API_KEY：从 Pixabay 下载场景图片；留空则跳过图片下载（仅填充结构化数据）；
# - SEEDKIT_CONFIG：统一业务数据配置文件路径（本地脚本与线上中台触发加载同一份）；
# - SEEDKIT_CACHE_DIR：Pixabay 检索结果与图片的本地缓存目录。
PIXABAY_API_KEY = env("PIXABAY_API_KEY", default="")
SEEDKIT_CONFIG = BASE_DIR / env("SEEDKIT_CONFIG", default="seeds/seed_data.yml")
SEEDKIT_CACHE_DIR = BASE_DIR / env("SEEDKIT_CACHE_DIR", default="media/seed_cache")

# ----------------------------- 后台主题全局配置 -----------------------------
# 依据 ADMIN_UI 合并对应主题的完整配置：
# - unfold：注入 UNFOLD dict（品牌 / 侧边栏导航 / 顶部栏开关 / 颜色主题 / 登录页）；
# - simpleui：注入 SIMPLEUI_* 平铺键（基础配置 + 关闭分析上报等净化项）。
# 具体键值定义见 utils/admin_theme.py，站点品牌联动 SITE_NAME / SITE_LOGO。
globals().update(
    build_theme_settings(
        ADMIN_UI,
        site_name=SITE_NAME,
        debug=DEBUG,
    )
)
