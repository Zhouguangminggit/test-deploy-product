"""本地开发配置。

继承 base.py，开启 DEBUG、放宽主机限制、使用 SQLite，并提升日志级别。
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, build_logging_config, env

DEBUG = False

# 开发环境放宽主机限制，便于本机与局域网访问
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=["*"])

# 开发数据库：SQLite（零配置，可随时删除重建）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# 开发环境不强制 HTTPS
SECURE_SSL_REDIRECT = False

# 开发环境默认 DEBUG 级别，可见业务调试日志（utils logger）；
# django 内部 logger 阈值不低于 INFO、django.utils.autoreload 固定 WARNING、
# django.db.backends 固定 INFO、django.server 固定 WARNING（见 build_logging_config），
# 避免文件监控/SQL 洪水与重复请求行。如需排查 SQL，临时在 utils/log.py 调低其级别即可。
LOG_LEVEL = env("LOG_LEVEL", default="DEBUG")
LOGGING = build_logging_config(LOG_LEVEL)
