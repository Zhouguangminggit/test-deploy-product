"""utils 应用配置。

在 AppConfig.ready() 中初始化 Loguru，使日志系统随 Django 应用注册自动装配，
业务代码无需手动调用 setup_loguru，即可通过 `from loguru import logger` 直接使用。
"""

from django.apps import AppConfig


class UtilsConfig(AppConfig):
    """通用能力层应用。"""

    name = "utils"
    verbose_name = "通用能力层"
    # utils/apps.py 中存在多个 AppConfig 时用于显式指定默认项（当前仅一个，保持明确）
    default = True

    def ready(self) -> None:
        # 延迟导入：ready() 阶段 settings 已加载完毕，可安全读取
        from django.conf import settings

        from .log import setup_loguru

        setup_loguru(
            level=getattr(settings, "LOG_LEVEL", "INFO"),
            # 空字符串归一化为 None，表示不启用文件日志（仅控制台）
            log_dir=getattr(settings, "LOG_DIR", "") or None,
            # 异常回溯是否展示变量值：跟随 DEBUG，生产（DEBUG=False）自动关闭以免泄露敏感信息
            diagnose=getattr(settings, "DEBUG", False),
        )
