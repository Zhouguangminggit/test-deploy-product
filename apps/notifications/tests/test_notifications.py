"""消息通知模块测试。

覆盖：定向消息 / 全站公告 / 事件通知的发送与收件记录、已读与全部已读、
软删除隔离、用户间权限隔离、路由访问（列表/详情打开即已读/删除）、
注册欢迎事件、导航栏未读角标。
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.notifications.models import Message, MessageAudience, MessageLevel, MessageRecipient
from apps.notifications.selectors import inbox, unread_count
from apps.notifications.services import (
    delete_for_user,
    mark_all_read,
    mark_read,
    notify_user,
    publish_announcement,
    send_message,
)

User = get_user_model()

PASSWORD = "StrongPwd123"


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", password=PASSWORD, nickname="爱丽丝")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", password=PASSWORD, nickname="鲍勃")


# ----------------------------- services 层 -----------------------------
@pytest.mark.django_db
def test_send_message_creates_recipients(alice, bob):
    message = send_message("测试标题", "测试正文", recipients=[alice, bob])
    assert message.audience == MessageAudience.DIRECTED
    assert MessageRecipient.objects.filter(message=message).count() == 2


@pytest.mark.django_db
def test_send_message_deduplicates_within_one_message(alice):
    # 同一用户重复出现在收件列表，唯一约束 + ignore_conflicts 仅产生一条记录
    message = send_message("重复", "内容", recipients=[alice, alice, alice])
    assert MessageRecipient.objects.filter(message=message, user=alice).count() == 1


@pytest.mark.django_db
def test_publish_announcement_expands_to_all_active_users(alice, bob):
    admin = User.objects.create_user(username="admin0", password=PASSWORD, is_active=True)
    inactive = User.objects.create_user(username="gone", password=PASSWORD, is_active=False)
    message = publish_announcement("公告", "全站公告内容")
    assert message.audience == MessageAudience.ANNOUNCEMENT
    recipients = set(
        MessageRecipient.objects.filter(message=message).values_list("user_id", flat=True)
    )
    assert recipients == {alice.pk, bob.pk, admin.pk}
    assert inactive.pk not in recipients


@pytest.mark.django_db
def test_notify_user_uses_system_audience(alice):
    message = notify_user(alice, "系统", "事件内容", level=MessageLevel.SUCCESS)
    assert message.audience == MessageAudience.SYSTEM
    assert message.level == MessageLevel.SUCCESS
    assert unread_count(alice) == 1


# ----------------------------- 已读 / 删除 -----------------------------
@pytest.mark.django_db
def test_mark_read_and_mark_all_read(alice, bob):
    notify_user(alice, "a1", "内容")
    notify_user(alice, "a2", "内容")
    notify_user(bob, "b1", "内容")

    entry = inbox(alice).first()
    mark_read(entry)
    entry.refresh_from_db()
    assert entry.is_read and entry.read_at is not None
    assert unread_count(alice) == 1

    updated = mark_all_read(alice)
    assert updated == 1
    assert unread_count(alice) == 0
    # 不影响其他用户
    assert unread_count(bob) == 1


@pytest.mark.django_db
def test_delete_is_soft_and_per_user(alice, bob):
    message = send_message("共享消息", "内容", recipients=[alice, bob])
    entry = MessageRecipient.objects.get(message=message, user=alice)
    delete_for_user(entry)
    assert MessageRecipient.objects.filter(pk=entry.pk).exists()  # 记录仍在，仅标记删除
    entry.refresh_from_db()
    assert entry.deleted
    # alice 收件箱不可见，bob 仍可见
    assert not inbox(alice).filter(message=message).exists()
    assert inbox(bob).filter(message=message).exists()


# ----------------------------- 路由 / 视图 -----------------------------
@pytest.mark.django_db
def test_list_view_requires_login(client):
    resp = client.get("/notifications/")
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_detail_view_marks_read(client, alice):
    notify_user(alice, "详情", "正文内容")
    entry = MessageRecipient.objects.get(user=alice)
    c = Client()
    c.force_login(alice)
    resp = c.get(f"/notifications/{entry.pk}/")
    assert resp.status_code == 200
    assert "正文内容" in resp.content.decode()
    entry.refresh_from_db()
    assert entry.is_read


@pytest.mark.django_db
def test_detail_view_blocks_other_user(client, alice, bob):
    notify_user(alice, "私密", "内容")
    entry = MessageRecipient.objects.get(user=alice)
    c = Client()
    c.force_login(bob)
    resp = c.get(f"/notifications/{entry.pk}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_delete_view_post(client, alice):
    notify_user(alice, "待删除", "内容")
    entry = MessageRecipient.objects.get(user=alice)
    c = Client()
    c.force_login(alice)
    resp = c.post(f"/notifications/{entry.pk}/delete/")
    assert resp.status_code == 302
    entry.refresh_from_db()
    assert entry.deleted


@pytest.mark.django_db
def test_mark_all_read_view(client, alice):
    notify_user(alice, "1", "内容")
    notify_user(alice, "2", "内容")
    c = Client()
    c.force_login(alice)
    resp = c.post("/notifications/read-all/")
    assert resp.status_code == 302
    assert unread_count(alice) == 0


@pytest.mark.django_db
def test_unread_badge_in_navbar(client, alice):
    notify_user(alice, "角标", "内容")
    c = Client()
    c.force_login(alice)
    body = c.get("/").content.decode()
    assert "消息通知" in body
    # 未读角标显示 1
    assert "badge-error" in body and ">1</span>" in body


# ----------------------------- 事件自动通知 -----------------------------
@pytest.mark.django_db
def test_register_sends_welcome_notification(client):
    resp = client.post(
        "/accounts/register/",
        {
            "username": "newbie",
            "nickname": "新人",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert resp.status_code == 302
    newbie = User.objects.get(username="newbie")
    msg = Message.objects.filter(recipients=newbie, audience=MessageAudience.SYSTEM).first()
    assert msg is not None
    assert "欢迎" in msg.title
