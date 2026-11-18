"""Gunicorn 访问日志设置。"""

from gunicorn.glogging import Logger


class AccessLogger(Logger):
    def access(self, resp, req, environ, request_time):
        # 只省略容器内探针正常返回的记录，保留外部检查和非 200 响应。
        if (
            environ.get("REQUEST_METHOD") == "GET"
            and environ.get("PATH_INFO") == "/healthz/"
            and environ.get("REMOTE_ADDR") == "127.0.0.1"
            and environ.get("HTTP_USER_AGENT") == "django-scaffold-healthcheck"
            and getattr(resp, "status_code", None) == 200
        ):
            return
        super().access(resp, req, environ, request_time)
