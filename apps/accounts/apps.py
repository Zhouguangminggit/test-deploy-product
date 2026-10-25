"""用户账户模块应用配置。

label 显式设为 "accounts"，使 AUTH_USER_MODEL 可写为 "accounts.User"。
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """用户账户应用。"""

    name = "apps.accounts"
    label = "accounts"
    verbose_name = "用户账户"
