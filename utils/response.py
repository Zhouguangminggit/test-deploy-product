"""通用响应辅助方法。

统一 JSON 响应结构 {code, message, data}，供 AJAX / 接口调用使用。
服务端渲染页面请直接用 render()；本模块仅处理 JSON 场景。
"""

from typing import Any

from django.http import JsonResponse

from .constants import RESPONSE_CODE_ERROR, RESPONSE_CODE_SUCCESS

# 保证中文不被转义为 \uXXXX
_DUMPS_PARAMS = {"ensure_ascii": False}


def success(
    data: Any = None,
    message: str = "ok",
    code: int = RESPONSE_CODE_SUCCESS,
    status: int = 200,
    **extra: Any,
) -> JsonResponse:
    """成功响应。extra 会平铺进响应体顶层。"""
    payload: dict[str, Any] = {"code": code, "message": message, "data": data}
    payload.update(extra)
    return JsonResponse(payload, status=status, json_dumps_params=_DUMPS_PARAMS)


def error(
    message: str = "error",
    code: int = RESPONSE_CODE_ERROR,
    data: Any = None,
    status: int = 400,
    **extra: Any,
) -> JsonResponse:
    """错误响应。extra 会平铺进响应体顶层。"""
    payload: dict[str, Any] = {"code": code, "message": message, "data": data}
    payload.update(extra)
    return JsonResponse(payload, status=status, json_dumps_params=_DUMPS_PARAMS)


# 语义化别名
ok = success
fail = error
