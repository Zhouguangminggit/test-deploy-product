from django.apps import AppConfig
from django.conf import settings
from loguru import logger


class LicensingConfig(AppConfig):
    name = "apps.licensing"
    label = "licensing"
    verbose_name = "产品授权"

    def ready(self):
        if settings.SETTINGS_MODULE == "config.settings.prod":
            logger.info("产品授权免检状态：{}", "开启" if settings.LICENSE_BYPASS else "关闭")
