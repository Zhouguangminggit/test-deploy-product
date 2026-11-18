"""操作日志装饰器（显式埋点）。

用法（置于权限装饰器内侧，贴近视图函数）：

    @login_required
    @log_operation(OperationAction.FILE_DELETE, module="files")
    def delete_view(request, pk):
        ...
        request.audit_detail = entry.original_name   # 可选：补充操作对象描述
        ...

actor 解析：登录类操作在视图内 login()/logout() 会改变 request.user，
因此同时捕获调用前后的用户，取已认证的一方，兼容登录与登出两种场景。
"""

import functools
from collections.abc import Callable

from .services import record_operation


def log_operation(
    action: str,
    *,
    module: str = "",
    object_repr: str | Callable = "",
    message: str = "",
):
    """记录被装饰视图的一次操作日志（视图正常返回后写入）。

    - object_repr：静态字符串，或接收 (request, args, kwargs) 的可调用；
    - 视图内可通过设置 request.audit_detail 动态覆盖操作对象描述。
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user_before = getattr(request, "user", None)
            response = view_func(request, *args, **kwargs)
            user_after = getattr(request, "user", None)

            actor = user_after if getattr(user_after, "is_authenticated", False) else user_before

            detail = object_repr(request, args, kwargs) if callable(object_repr) else object_repr
            detail = getattr(request, "audit_detail", "") or detail

            record_operation(
                request,
                action,
                module=module,
                object_repr=detail,
                message=message,
                user=actor,
            )
            return response

        return _wrapped

    return decorator
