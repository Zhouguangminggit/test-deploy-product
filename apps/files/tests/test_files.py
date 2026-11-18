"""文件管理模块测试。

覆盖：上传落盘、列表可见性隔离、下载权限、删除清理物理文件、
超大 / 非法类型拒绝、服务函数直接复用。
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.files.models import FileCategory, FileEntry
from apps.files.services import delete_file, save_upload

User = get_user_model()

PASSWORD = "StrongPwd123"


def _upload(name="report.txt", content=b"hello", content_type="text/plain"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", password=PASSWORD)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="admin2", password=PASSWORD, is_staff=True)


# ----------------------------- services 直接复用 -----------------------------
@pytest.mark.django_db
def test_save_upload_creates_entry_and_file(alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    entry = save_upload(_upload(), user=alice, category=FileCategory.DOCUMENT)
    assert entry.pk
    assert entry.original_name == "report.txt"
    assert entry.size > 0
    assert entry.file.name.startswith(f"uploads/{alice.pk}/")
    assert entry.file.storage.exists(entry.file.name)


@pytest.mark.django_db
def test_save_upload_rejects_bad_extension(alice, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    with pytest.raises(ValidationError):
        save_upload(_upload(name="evil.exe"), user=alice)


@pytest.mark.django_db
def test_save_upload_rejects_oversize(alice, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    big = _upload(name="big.txt", content=b"x" * (2 * 1024 * 1024))
    with pytest.raises(ValidationError):
        save_upload(big, user=alice, max_bytes=1024)


@pytest.mark.django_db
def test_delete_file_removes_physical(alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    entry = save_upload(_upload(), user=alice)
    stored = entry.file.name
    delete_file(entry)
    assert not FileEntry.objects.filter(pk=entry.pk).exists()
    assert not entry.file.storage.exists(stored)


# ----------------------------- 视图：列表可见性 -----------------------------
@pytest.mark.django_db
def test_list_only_own_files(client, alice, admin_user, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    save_upload(_upload(name="mine.txt"), user=alice)
    save_upload(_upload(name="theirs.txt"), user=admin_user)

    client.force_login(alice)
    body = client.get("/files/").content.decode()
    assert "mine.txt" in body
    assert "theirs.txt" not in body


@pytest.mark.django_db
def test_admin_sees_all_files(client, alice, admin_user, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    save_upload(_upload(name="mine.txt"), user=alice)

    client.force_login(admin_user)
    body = client.get("/files/").content.decode()
    assert "mine.txt" in body


# ----------------------------- 视图：上传 / 下载 / 删除 -----------------------------
@pytest.mark.django_db
def test_upload_view(client, alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(alice)
    resp = client.post("/files/upload/", {"file": _upload(name="up.txt"), "category": "document"})
    assert resp.status_code == 302
    assert FileEntry.objects.filter(uploader=alice, original_name="up.txt").exists()


@pytest.mark.django_db
def test_download_permission(client, alice, admin_user, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    entry = save_upload(_upload(name="secret.txt"), user=alice)

    # 他人（非 staff）无法下载
    client.force_login(admin_user)
    other = User.objects.create_user(username="mallory", password=PASSWORD, is_staff=False)
    client.force_login(other)
    assert client.get(f"/files/{entry.pk}/download/").status_code == 404

    # 本人可下载
    client.force_login(alice)
    resp = client.get(f"/files/{entry.pk}/download/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_delete_view_removes_entry(client, alice, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    entry = save_upload(_upload(name="del.txt"), user=alice)
    client.force_login(alice)
    resp = client.post(f"/files/{entry.pk}/delete/")
    assert resp.status_code == 302
    assert not FileEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_list_requires_login(client):
    resp = client.get("/files/")
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]
