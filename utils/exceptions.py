"""自定义通用异常。

统一 code / message / status_code 结构，便于响应层与错误处理集中转换，
避免在业务代码中散落地拼装 HTTP 响应。
"""

from typing import Any


class AppError(Exception):
    """业务异常基类。

    - code：业务错误码（与 HTTP 状态码解耦）
    - message：可直接展示给用户的提示
    - status_code：映射的 HTTP 状态码
    - data：可选的附加数据（如字段级错误）
    """

    default_code: int = 1
    default_message: str = "服务器内部错误"
    default_status: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        code: int | None = None,
        status_code: int | None = None,
        data: Any = None,
    ) -> None:
        self.message = message if message is not None else self.default_message
        self.code = code if code is not None else self.default_code
        self.status_code = status_code if status_code is not None else self.default_status
        self.data = data
        super().__init__(self.message)


class ValidationError(AppError):
    """请求参数校验失败。"""

    default_code = 1001
    default_message = "请求参数校验失败"
    default_status = 400


class UnauthorizedError(AppError):
    """未认证或登录已失效。"""

    default_code = 1002
    default_message = "未认证或登录已失效"
    default_status = 401


class PermissionDeniedError(AppError):
    """没有访问权限。"""

    default_code = 1003
    default_message = "没有访问权限"
    default_status = 403


class NotFoundError(AppError):
    """资源不存在。"""

    default_code = 1004
    default_message = "资源不存在"
    default_status = 404


class ConflictError(AppError):
    """资源冲突（如唯一约束）。"""

    default_code = 1009
    default_message = "资源冲突"
    default_status = 409
