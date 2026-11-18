"""utils 通用能力层单元测试。"""

import json
from datetime import UTC, datetime

import pytest
from django.core.exceptions import ValidationError

from utils import date_time, file_helpers, helpers, pagination, security
from utils.enums import CommonStatus, SortOrder
from utils.exceptions import AppError, NotFoundError
from utils.response import error, success
from utils.validators import (
    validate_file_extension,
    validate_password_strength,
    validate_phone,
    validate_username,
)

UTC = UTC


# ----------------------------- helpers -----------------------------
def test_deep_merge_does_not_mutate_input():
    base = {"a": 1, "b": {"x": 1, "y": 2}}
    override = {"b": {"y": 20, "z": 30}, "c": 3}
    result = helpers.deep_merge(base, override)
    assert result == {"a": 1, "b": {"x": 1, "y": 20, "z": 30}, "c": 3}
    assert base == {"a": 1, "b": {"x": 1, "y": 2}}


def test_camel_snake_conversion():
    assert helpers.camel_to_snake("userName") == "user_name"
    assert helpers.snake_to_camel("user_name") == "userName"
    assert helpers.snake_to_camel("user_name", upper_first=True) == "UserName"


def test_chunks():
    assert list(helpers.chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    with pytest.raises(ValueError):
        list(helpers.chunks([1], 0))


def test_truncate_and_safe_int():
    assert helpers.truncate("abcdef", 5) == "ab..."
    assert helpers.truncate("abc", 5) == "abc"
    assert helpers.safe_int("12") == 12
    assert helpers.safe_int("x", 3) == 3


# ----------------------------- file_helpers -----------------------------
def test_human_readable_size():
    assert file_helpers.human_readable_size(0) == "0 B"
    assert file_helpers.human_readable_size(512) == "512 B"
    assert file_helpers.human_readable_size(1024) == "1.0 KiB"
    assert file_helpers.human_readable_size(1536) == "1.5 KiB"


def test_sanitize_filename_strips_path_and_unsafe_chars():
    assert file_helpers.sanitize_filename("../../etc/passwd") == "passwd"
    cleaned = file_helpers.sanitize_filename("a b/c?.txt")
    assert "/" not in cleaned
    assert "?" not in cleaned


def test_extension_helpers():
    assert file_helpers.get_extension("a.TXT") == ".txt"
    assert file_helpers.get_extension("noext") == ""
    assert file_helpers.is_extension_allowed("a.PNG", {".png", ".jpg"}) is True
    assert file_helpers.is_extension_allowed("a.exe", {".png"}) is False


def test_generate_unique_filename_keeps_ext():
    name = file_helpers.generate_unique_filename("photo.JPG")
    assert name.endswith(".jpg")
    assert len(name) > len(".jpg")


# ----------------------------- security -----------------------------
def test_generate_random_string_and_token():
    assert len(security.generate_random_string(12)) == 12
    assert len(security.generate_token(32)) > 20
    with pytest.raises(ValueError):
        security.generate_random_string(8, letters=False, digits=False)


def test_mask_sensitive_and_email():
    assert security.mask_sensitive("13812345678", 3, 4) == "138****5678"
    assert security.mask_sensitive("abc") == "***"
    assert security.mask_email("zhangsan@example.com") == "z******n@example.com"


def test_password_policy():
    ok, _ = security.password_meets_policy("abcd1234")
    assert ok is True
    ok2, errors = security.password_meets_policy("abc")
    assert ok2 is False and errors


def test_constant_time_equals():
    assert security.constant_time_equals("a", "a") is True
    assert security.constant_time_equals("a", "b") is False


# ----------------------------- validators -----------------------------
def test_validate_phone():
    assert validate_phone("13812345678") == "13812345678"
    with pytest.raises(ValidationError):
        validate_phone("123")


def test_validate_username():
    assert validate_username("user_01") == "user_01"
    with pytest.raises(ValidationError):
        validate_username("ab")


def test_validate_file_extension():
    assert validate_file_extension("a.png", {".png"}) == "a.png"
    with pytest.raises(ValidationError):
        validate_file_extension("a.exe", {".png"})


def test_validate_password_strength():
    assert validate_password_strength("abcd1234") == "abcd1234"
    with pytest.raises(ValidationError):
        validate_password_strength("123")


# ----------------------------- date_time -----------------------------
def test_format_datetime_uses_local_timezone():
    # Asia/Shanghai = UTC+8（dev 默认时区）
    dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert date_time.format_datetime(dt) == "2024-01-01 08:00:00"


def test_format_date_crosses_day():
    dt = datetime(2024, 1, 1, 20, 0, 0, tzinfo=UTC)
    assert date_time.format_date(dt) == "2024-01-02"


def test_days_between_and_timestamp_roundtrip():
    d1 = datetime(2024, 1, 1, tzinfo=UTC)
    d2 = datetime(2024, 1, 10, tzinfo=UTC)
    assert date_time.days_between(d1, d2) == 9

    dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert date_time.from_timestamp(date_time.timestamp_ms(dt) / 1000) == dt


# ----------------------------- pagination -----------------------------
def test_paginate_basic():
    result = pagination.paginate(list(range(95)), page=2, page_size=10)
    assert result.total == 95
    assert result.page == 2
    assert result.total_pages == 10
    assert result.items == list(range(10, 20))
    assert result.has_previous and result.has_next


def test_paginate_invalid_page_falls_back():
    data = list(range(5))
    assert pagination.paginate(data, page="abc", page_size=2).page == 1
    last = pagination.paginate(data, page=999, page_size=2)
    assert last.page == last.total_pages


def test_page_size_capped():
    result = pagination.paginate(list(range(1000)), page=1, page_size=100000)
    assert result.page_size == 100


def test_compute_page_range_includes_edges():
    result = pagination.compute_page_range(current=5, total_pages=20, window=2)
    assert result == sorted(result)
    assert 1 in result and 20 in result and 5 in result


# ----------------------------- response -----------------------------
def test_response_success_envelope():
    resp = success(data={"id": 1}, message="创建成功")
    assert resp.status_code == 200
    payload = json.loads(resp.content.decode())
    assert payload == {"code": 0, "message": "创建成功", "data": {"id": 1}}


def test_response_error_and_chinese_not_escaped():
    resp = error(message="出错", status=400)
    assert resp.status_code == 400
    assert json.loads(resp.content.decode())["code"] == 1
    assert "你好".encode() in success(message="你好").content


# ----------------------------- enums & exceptions -----------------------------
def test_enums_are_str():
    assert CommonStatus.ENABLED == "enabled"
    assert str(SortOrder.DESC) == "desc"


def test_exception_defaults_and_override():
    err = NotFoundError()
    assert err.status_code == 404 and err.code == 1004
    custom = AppError("自定义", code=999, status_code=418)
    assert (custom.message, custom.code, custom.status_code) == ("自定义", 999, 418)
