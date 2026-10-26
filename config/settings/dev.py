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

# 异步任务（Celery）：开发默认连团队共享 Redis 实例（约定用 db1，与生产 db0 区隔）。
# 将 .env 的 REDIS_URL 填为形如 redis://:密码@共享实例地址:6379/1；
# 未配置时回退本机 redis://localhost:6379/1（worker 未启动不影响 Web 进程存活）。
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")
CELERY_BROKER_URL = REDIS_URL
# eager（同步）执行时也回写结果到 backend：仅当 task_always_eager=True 时生效（pytest 全局夹具），
# 真实 worker 走异步投递不受影响；便于测试中用 AsyncResult(task_id) 回查 django-db 落库结果。
CELERY_TASK_STORE_EAGER_RESULT = True

# 开发环境默认 DEBUG 级别，可见业务调试日志（utils logger）；
# django 内部 logger 阈值不低于 INFO、django.utils.autoreload 固定 WARNING、
# django.db.backends 固定 INFO、django.server 固定 WARNING（见 build_logging_config），
# 避免文件监控/SQL 洪水与重复请求行。如需排查 SQL，临时在 utils/log.py 调低其级别即可。
LOG_LEVEL = env("LOG_LEVEL", default="DEBUG")
LOGGING = build_logging_config(LOG_LEVEL)
