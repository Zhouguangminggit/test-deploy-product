"""数据初始化模块应用配置。"""

from django.apps import AppConfig


class SeedkitConfig(AppConfig):
    """seedkit 数据初始化应用。"""

    name = "apps.seedkit"
    label = "seedkit"
    verbose_name = "数据初始化"
