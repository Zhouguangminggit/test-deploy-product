"""用户账户模型。

以自定义 User(AbstractUser) 作为全站用户模型（AUTH_USER_MODEL = "accounts.User"）。
在 Django 内置字段基础上扩展昵称、头像、手机号，供导航栏与个人中心使用。
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """全站用户模型。"""

    nickname = models.CharField("昵称", max_length=50, blank=True)
    avatar = models.ImageField("头像", upload_to="avatars/%Y%m/", blank=True)
    phone = models.CharField("手机号", max_length=20, blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = "用户"
        verbose_name_plural = "用户"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        """展示名：优先昵称，回退用户名。供导航栏与模板统一取用。"""
        return self.nickname or self.username
