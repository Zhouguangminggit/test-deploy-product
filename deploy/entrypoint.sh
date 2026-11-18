#!/bin/sh
# 容器启动脚本：等待数据库 -> 迁移 -> 收集静态文件 -> 启动 Gunicorn
set -e

# 使用 SQLite 或无需等待数据库时，设置 SKIP_DB_WAIT=1 跳过等待
if [ "${SKIP_DB_WAIT:-0}" != "1" ]; then
    echo "==> 等待数据库就绪..."
    python - <<'PY'
import socket
import time

from django.conf import settings

database = settings.DATABASES["default"]
host = database["HOST"]
if not host or host.startswith("/"):
    raise SystemExit(0)
port = int(database["PORT"] or 3306)
for _ in range(30):
    try:
        socket.create_connection((host, port), timeout=2).close()
        print("数据库已就绪")
        break
    except OSError:
        time.sleep(1)
else:
    print("数据库连接超时，仍将尝试继续")
PY
fi

echo "==> 应用数据库迁移..."
python manage.py migrate --noinput

echo "==> 收集静态文件..."
# css/base.css 是 Tailwind 源码（含 @import/@plugin），不入 collectstatic；
# 模板引用的是编译产物 css/dist/base.css。
python manage.py collectstatic --noinput --ignore "css/base.css"

echo "==> 启动 Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile -
