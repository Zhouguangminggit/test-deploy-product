"""操作日志模块测试。

覆盖：装饰器对登录 / 登出 / 注册的记录、文件上传 / 删除记录、
匿名（登录失败）不记录、record_operation 直接调用、后台只读权限。
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from apps.audit.models import OperationAction, OperationLog
from apps.audit.services import record_operation

User = get_user_model()

PASSWORD = "StrongPwd123"


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", password=PASSWORD)


# ----------------------------- 认证类埋点 -----------------------------
@pytest.mark.django_db
def test_login_records_log(client, alice):
    client.post("/accounts/login/", {"username": "alice", "password": PASSWORD})
    log = OperationLog.objects.filter(action=OperationAction.LOGIN).first()
    assert log is not None
    assert log.user == alice
    assert log.username == "alice"
    assert log.module == "accounts"


@pytest.mark.django_db
def test_failed_login_not_recorded(client, alice):
    client.post("/accounts/login/", {"username": "alice", "password": "wrong-pass"})
    assert not OperationLog.objects.filter(action=OperationAction.LOGIN).exists()


@pytest.mark.django_db
def test_logout_records_authenticated_user(client, alice):
    client.force_login(alice)
    client.post("/accounts/logout/")
    log = OperationLog.objects.filter(action=OperationAction.LOGOUT).first()
    assert log is not None
    assert log.user == alice


@pytest.mark.django_db
def test_register_records_log(client):
    client.post(
        "/accounts/register/",
        {"username": "bob", "nickname": "Bob", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert OperationLog.objects.filter(action=OperationAction.REGISTER, username="bob").exists()


# ----------------------------- 业务写操作埋点 -----------------------------
@pytest.mark.django_db
def test_file_upload_records_log(client, alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(alice)
    client.post(
        "/files/upload/",
        {
            "file": SimpleUploadedFile("doc.txt", b"x", content_type="text/plain"),
            "category": "document",
        },
    )
    log = OperationLog.objects.filter(action=OperationAction.FILE_UPLOAD).first()
    assert log is not None
    assert log.object_repr == "doc.txt"


@pytest.mark.django_db
def test_file_delete_records_log(client, alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    from apps.files.services import save_upload

    entry = save_upload(SimpleUploadedFile("del.txt", b"x"), user=alice)
    client.force_login(alice)
    client.post(f"/files/{entry.pk}/delete/")
    log = OperationLog.objects.filter(action=OperationAction.FILE_DELETE).first()
    assert log is not None
    assert log.object_repr == "del.txt"


# ----------------------------- services 直接调用 -----------------------------
def test_record_operation_skips_anonymous():
    request = RequestFactory().get("/")

    class Anon:
        is_authenticated = False

    request.user = Anon()
    assert record_operation(request, OperationAction.LOGIN) is None


@pytest.mark.django_db
def test_record_operation_with_user(alice):
    request = RequestFactory().get("/", headers={"user-agent": "pytest-agent"})
    request.user = alice
    request.request_id = "abc123"
    log = record_operation(request, OperationAction.LOGIN, module="accounts", object_repr="obj")
    assert log is not None
    assert log.user_agent == "pytest-agent"
    assert log.request_id == "abc123"


# ----------------------------- 后台只读权限 -----------------------------
@pytest.mark.django_db
def test_admin_read_only(alice):
    from django.contrib import admin

    from apps.audit.admin import OperationLogAdmin

    site = admin.site
    model_admin = site._registry[OperationLog]
    request = RequestFactory().get("/admin/")
    request.user = alice
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert isinstance(model_admin, OperationLogAdmin)
