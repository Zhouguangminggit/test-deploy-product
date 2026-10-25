"""日期时间处理工具。

统一使用 Django 的时区感知 API（django.utils.timezone），
避免混用 naive / aware datetime 造成的时区错乱。
"""

from datetime import UTC, date, datetime, time, timedelta

from django.utils import timezone

from .constants import DATE_FORMAT, DATETIME_FORMAT, DATETIME_FORMAT_MINUTE


def now() -> datetime:
    """当前时区感知时间（UTC aware）。"""
    return timezone.now()


def to_local(value: datetime | None) -> datetime | None:
    """转换为项目当前时区（settings.TIME_ZONE）的 aware datetime。"""
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def format_datetime(value: datetime | None, fmt: str = DATETIME_FORMAT) -> str:
    """格式化 datetime 为字符串（先转本地时区）；空值返回空串。"""
    if not value:
        return ""
    return to_local(value).strftime(fmt)


def format_datetime_minute(value: datetime | None) -> str:
    """格式化到分钟。"""
    return format_datetime(value, DATETIME_FORMAT_MINUTE)


def format_date(value: date | datetime | None, fmt: str = DATE_FORMAT) -> str:
    """格式化 date/datetime 的日期部分；空值返回空串。"""
    if not value:
        return ""
    if isinstance(value, datetime):
        value = to_local(value).date()
    return value.strftime(fmt)


def start_of_day(value: datetime | None = None) -> datetime:
    """返回给定时间（默认当前）所在自然日的 00:00:00（本地时区，aware）。"""
    local = to_local(value) or timezone.localtime(now())
    naive = datetime.combine(local.date(), time.min)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def end_of_day(value: datetime | None = None) -> datetime:
    """返回给定时间（默认当前）所在自然日的 23:59:59.999999（本地时区，aware）。"""
    local = to_local(value) or timezone.localtime(now())
    naive = datetime.combine(local.date(), time.max)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def days_between(start: date | datetime, end: date | datetime) -> int:
    """计算两个日期相差的自然天数（绝对值）。"""
    start_date = start.date() if isinstance(start, datetime) else start
    end_date = end.date() if isinstance(end, datetime) else end
    return abs((end_date - start_date).days)


def add_days(value: datetime | None, days: int) -> datetime:
    """在给定时间上加减天数。"""
    base = value or now()
    return base + timedelta(days=days)


def timestamp_ms(value: datetime | None = None) -> int:
    """转为毫秒级时间戳。"""
    return int((value or now()).timestamp() * 1000)


def from_timestamp(seconds: float) -> datetime:
    """由秒级时间戳构造 aware datetime（UTC）。"""
    return datetime.fromtimestamp(seconds, tz=UTC)
