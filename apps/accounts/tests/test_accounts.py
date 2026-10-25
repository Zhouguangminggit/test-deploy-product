"""用户账户模块测试。

覆盖注册（成功/重复）、登录（成功/失败）、个人中心需登录、
资料编辑（昵称/头像上传）、修改密码。
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

User = get_user_model()

PASSWORD = "StrongPwd123"


@pytest.fixture
def user(db):
    return User.objects.create_user(username="alice", password=PASSWORD, nickname="Alice")


def _png_upload(name="avatar.png") -> SimpleUploadedFile:
    """生成一张合法 PNG 作为上传文件。"""
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), (200, 120, 40)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


# ----------------------------- 注册 -----------------------------
@pytest.mark.django_db
def test_register_success(client):
    resp = client.post(
        "/accounts/register/",
        {
            "username": "bob",
            "nickname": "Bob",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert resp.status_code == 302
    assert User.objects.filter(username="bob").exists()


@pytest.mark.django_db
def test_register_duplicate_username(client):
    User.objects.create_user(username="bob", password=PASSWORD)
    resp = client.post(
        "/accounts/register/",
        {
            "username": "bob",
            "nickname": "Bob",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    # 表单校验失败，重新渲染注册页而非重定向
    assert resp.status_code == 200
    # 重复用户名不会被创建，仍只有最初的一个
    assert User.objects.filter(username="bob").count() == 1


# ----------------------------- 登录 -----------------------------
@pytest.mark.django_db
def test_login_success(client, user):
    resp = client.post("/accounts/login/", {"username": "alice", "password": PASSWORD})
    assert resp.status_code == 302
    assert resp.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_login_failure(client, user):
    resp = client.post("/accounts/login/", {"username": "alice", "password": "wrong-pass"})
    assert resp.status_code == 200
    assert not resp.wsgi_request.user.is_authenticated


# ----------------------------- 个人中心 -----------------------------
@pytest.mark.django_db
def test_profile_update_nickname(client, user):
    client.force_login(user)
    resp = client.post(
        "/accounts/profile/",
        {"form": "profile", "nickname": "新昵称", "email": "", "phone": ""},
    )
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.nickname == "新昵称"


@pytest.mark.django_db
def test_profile_update_avatar(client, user):
    client.force_login(user)
    resp = client.post(
        "/accounts/profile/",
        {
            "form": "profile",
            "nickname": user.nickname,
            "email": "",
            "phone": "",
            "avatar": _png_upload(),
        },
    )
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.avatar  # 头像已保存
    # 头像被压缩到 512px 以内
    with Image.open(user.avatar.path) as img:
        assert max(img.size) <= 512


@pytest.mark.django_db
def test_password_change(client, user):
    client.force_login(user)
    new_password = "EvenStronger456"
    resp = client.post(
        "/accounts/profile/",
        {
            "form": "password",
            "old_password": PASSWORD,
            "new_password1": new_password,
            "new_password2": new_password,
        },
    )
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.check_password(new_password)
