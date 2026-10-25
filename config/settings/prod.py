"""生产环境配置。

继承 base.py，关闭 DEBUG，使用 MySQL（PyMySQL 驱动），并进行安全加固。
所有敏感项均来自环境变量；HTTPS 相关开关默认关闭，以便纯 HTTP 的容器编排演示可正常运行，
正式启用 HTTPS 后请通过环境变量将 SECURE_SSL_REDIRECT / *_COOKIE_SECURE / SECURE_HSTS_SECONDS 打开。
"""

from .base import *  # noqa: F401,F403
from .base import build_logging_config, env

DEBUG = False

# 生产必须显式配置允许的主机（多个以逗号分隔）
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])

# ----------------------------- 数据库（MySQL）-----------------------------
# 优先使用 DATABASE_URL；否则由 MYSQL_* 变量组合。
_database_url = env("DATABASE_URL", default=None)
if _database_url:
    DATABASES = {"default": env.db_url()}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("MYSQL_DATABASE", default="django_scaffold"),
            "USER": env("MYSQL_USER", default="root"),
            "PASSWORD": env("MYSQL_PASSWORD", default=""),
            "HOST": env("MYSQL_HOST", default="db"),
            "PORT": env("MYSQL_PORT", default="3306"),
            "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
            "OPTIONS": {
                "charset": "utf8mb4",
                # 严格模式，避免数据被隐式截断
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# ----------------------------- 安全加固 -----------------------------
# 位于 Nginx 反向代理之后，据此识别原始协议
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# HTTPS 相关（默认关闭，启用 HTTPS 后通过环境变量打开）
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

# ----------------------------- 邮件（SMTP）-----------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# ----------------------------- 日志（Loguru）-----------------------------
# 生产默认 INFO 级别、仅输出到控制台（stderr），交由 Docker / 日志采集系统统一收集；
# 如需落盘，设置环境变量 LOG_DIR 并确保容器已挂载对应卷（文件按日轮转、保留 14 天、zip 归档）。
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = build_logging_config(LOG_LEVEL)
