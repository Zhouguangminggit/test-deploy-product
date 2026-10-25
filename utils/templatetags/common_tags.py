"""通用模板标签与过滤器。

已在 settings.TEMPLATES.OPTIONS.builtins 中注册为全局内置库，
模板中可直接使用而无需 {% load common_tags %}。
"""

from django import template

from utils.constants import DATE_FORMAT, DATETIME_FORMAT_MINUTE
from utils.date_time import format_date, format_datetime
from utils.file_helpers import human_readable_size
from utils.security import mask_email, mask_sensitive

register = template.Library()


@register.filter(name="datetime_fmt")
def datetime_fmt(value, fmt: str | None = None) -> str:
    """格式化日期时间（默认精确到分钟）。用法：{{ obj.created_at|datetime_fmt }}"""
    return format_datetime(value, fmt or DATETIME_FORMAT_MINUTE)


@register.filter(name="date_fmt")
def date_fmt(value, fmt: str | None = None) -> str:
    """格式化日期。用法：{{ obj.birthday|date_fmt }}"""
    return format_date(value, fmt or DATE_FORMAT)


@register.filter(name="file_size")
def file_size(value) -> str:
    """字节数转可读大小。用法：{{ file.size|file_size }}"""
    return human_readable_size(value)


@register.filter(name="mask")
def mask(value, args: str = "3,4") -> str:
    """通用掩码，参数为“保留前N位,保留后M位”。用法：{{ phone|mask:"3,4" }}"""
    try:
        keep_start, keep_end = (int(part) for part in str(args).split(","))
    except ValueError:
        keep_start, keep_end = 3, 4
    return mask_sensitive(str(value or ""), keep_start, keep_end)


@register.filter(name="mask_email")
def mask_email_filter(value) -> str:
    """邮箱掩码。用法：{{ user.email|mask_email }}"""
    return mask_email(str(value or ""))


@register.filter(name="placeholder")
def placeholder(value, default: str = "-") -> str:
    """空值占位符。用法：{{ obj.nickname|placeholder:"未填写" }}"""
    if value is None or value == "":
        return default
    return value


@register.simple_tag(takes_context=True)
def nav_active(context, *patterns: str) -> str:
    """导航高亮：当前路径命中任一前缀则返回高亮样式类。

    - 模式为 "/" 时按精确匹配（避免命中所有路径）；
    - 其余模式按前缀匹配。
    用法：class="{% nav_active '/admin/' %}" 或 {% nav_active "/dashboard" "/home" as cls %}
    """
    request = context.get("request")
    if not request:
        return ""
    path = request.path
    for pattern in patterns:
        if not pattern:
            continue
        matched = path == "/" if pattern == "/" else path.startswith(pattern)
        if matched:
            return "font-semibold text-blue-600"
    return "text-gray-600 hover:text-blue-600"
