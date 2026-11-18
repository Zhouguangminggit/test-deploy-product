"""操作日志记录逻辑（services）。

统一入口 record_operation：从请求上下文提取 IP / UA / request_id，
写入 OperationLog。业务侧一般通过 @log_operation 装饰器间接调用。
"""

from django.contrib.auth import get_user_model
from loguru import logger

from utils.helpers import get_client_ip

from .models import OperationLog

User = get_user_model()


def record_operation(
    request,
    action: str,
    *,
    module: str = "",
    object_repr: str = "",
    message: str = "",
    user=None,
) -> OperationLog | None:
    """记录一条操作日志。actor 解析优先级：显式 user > request.user。

    匿名用户（未登录）不记录，返回 None，避免脏数据。
    """
    actor = user if user is not None else getattr(request, "user", None)
    if not actor or not getattr(actor, "is_authenticated", False):
        return None

    entry = OperationLog.objects.create(
        user=actor,
        username=getattr(actor, "username", ""),
        action=action,
        module=module,
        object_repr=(object_repr or "")[:255],
        message=(message or "")[:255],
        ip_address=get_client_ip(request) or None,
        user_agent=request.headers.get("User-Agent", "")[:256],
        request_id=getattr(request, "request_id", "") or "",
    )
    logger.info("操作日志：user={} action={} object={}", entry.username, action, object_repr)
    return entry
