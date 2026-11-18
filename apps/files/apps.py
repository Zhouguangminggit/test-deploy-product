"""文件管理模块应用配置。"""

from django.apps import AppConfig


class FilesConfig(AppConfig):
    """文件管理应用。"""

    name = "apps.files"
    label = "files"
    verbose_name = "文件管理"
