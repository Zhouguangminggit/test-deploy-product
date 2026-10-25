"""通用装饰器。

提供 AJAX 限制、匿名访问限制、执行计时等视图装饰器。
均使用 functools.wraps 保留原函数元信息，兼容函数视图与方法。
"""

import functools
import time

from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect
from loguru import logger


def ajax_required(view_func):
    """仅允许 AJAX 请求（X-Requested-With 或 Accept 含 application/json）。"""

    @functools.wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
        )
        if not is_ajax:
            return JsonResponse(
                {"code": 1, "message": "仅支持 AJAX 请求", "data": None},
                status=400,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def anonymous_required(view_func=None, *, redirect_url: str = "/"):
    """仅允许匿名（未登录）用户访问，如登录 / 注册页；已登录则重定向。

    支持带参或不带参两种用法：
        @anonymous_required
        @anonymous_required(redirect_url="/dashboard/")
    """

    def decorator(func):
        @functools.wraps(func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            if request.user.is_authenticated:
                return redirect(redirect_url)
            return func(request, *args, **kwargs)

        return _wrapped

    if view_func is not None:
        return decorator(view_func)
    return decorator


def timed(view_func):
    """记录视图执行耗时（毫秒），便于性能观测。"""

    @functools.wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        start = time.perf_counter()
        try:
            return view_func(request, *args, **kwargs)
        finally:
            cost_ms = (time.perf_counter() - start) * 1000
            logger.info("view={} cost={:.2f}ms path={}", view_func.__name__, cost_ms, request.path)

    return _wrapped
