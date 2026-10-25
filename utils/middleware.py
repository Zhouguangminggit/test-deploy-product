"""通用中间件。

- RequestMetaMiddleware：为每个请求分配 request-id（回写响应头），并记录请求耗时；
- request_id_var：请求级上下文变量（定义于 utils.log），贯穿视图与日志，实现全链路追踪。
"""

import time
import uuid

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from loguru import logger

from .constants import REQUEST_ID_HEADER, REQUEST_ID_LENGTH
from .log import request_id_var


class RequestMetaMiddleware(MiddlewareMixin):
    """注入 request-id 并记录请求耗时。"""

    def process_request(self, request: HttpRequest) -> None:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:REQUEST_ID_LENGTH]
        request.request_id = request_id  # type: ignore[attr-defined]
        request._start_time = time.perf_counter()  # type: ignore[attr-defined]
        request_id_var.set(request_id)

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        request_id = getattr(request, "request_id", None)
        if request_id:
            response[REQUEST_ID_HEADER] = request_id

        start = getattr(request, "_start_time", None)
        if start is not None:
            cost_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "{} {} -> {} ({:.2f}ms)",
                request.method,
                request.get_full_path(),
                response.status_code,
                cost_ms,
            )

        # 复位上下文变量，避免线程复用时串味
        request_id_var.set("-")
        return response
