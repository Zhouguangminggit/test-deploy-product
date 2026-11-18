"""通用枚举"""

from enum import StrEnum, unique


@unique
class CommonStatus(StrEnum):
    """通用启用 / 禁用状态。"""

    ENABLED = "enabled"
    DISABLED = "disabled"


@unique
class SortOrder(StrEnum):
    """通用排序方向。"""

    ASC = "asc"
    DESC = "desc"
