"""用户账户业务逻辑（services）。

注册、资料更新（含头像压缩）、改密等操作集中于此，视图保持轻薄。
头像在落盘前用 Pillow 等比压缩至 512px 以内，控制演示站存储体积。
"""

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from loguru import logger

from utils.image_helpers import resize_image

User = get_user_model()

# 头像最长边像素（等比缩放上限）
AVATAR_MAX_SIZE = 512


def register_user(*, username: str, nickname: str, password: str) -> User:
    """创建普通用户（非超管）。密码经 create_user 自动哈希。"""
    user = User.objects.create_user(username=username, password=password)
    user.nickname = nickname
    user.save(update_fields=["nickname"])
    logger.info("用户注册成功：username={}", username)
    return user


def update_profile(
    user: User,
    *,
    nickname: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    avatar=None,
) -> User:
    """更新个人资料；avatar 提供时先压缩再保存。"""
    if nickname is not None:
        user.nickname = nickname
    if email is not None:
        user.email = email
    if phone is not None:
        user.phone = phone

    if avatar is not None:
        user.avatar = _compress_avatar(avatar)

    user.save()
    logger.info("资料更新成功：user_id={}", user.pk)
    return user


def change_password(user: User, *, old_password: str, new_password: str) -> User:
    """校验旧密码后设置新密码。校验失败抛出 django 表单层已处理，此处假定合法。"""
    user.set_password(new_password)
    user.save(update_fields=["password"])
    logger.info("密码修改成功：user_id={}", user.pk)
    return user


def _compress_avatar(uploaded) -> ContentFile:
    """将上传头像等比压缩到 AVATAR_MAX_SIZE 内，返回 ContentFile。

    压缩失败（非法图片）时回退保存原始文件，避免因图片库异常中断资料更新。
    """
    buffer = resize_image(uploaded, AVATAR_MAX_SIZE, AVATAR_MAX_SIZE, fmt="PNG", quality=90)
    if buffer is None:
        logger.warning("头像压缩失败，按原图保存：name={}", getattr(uploaded, "name", ""))
        return uploaded

    name = getattr(uploaded, "name", "avatar.png") or "avatar.png"
    stem = name.rsplit(".", 1)[0]
    content = buffer.read()
    return ContentFile(content, name=f"{stem}.png")
