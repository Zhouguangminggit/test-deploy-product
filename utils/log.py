"""日志系统（基于 Loguru）。

统一后端日志出口，替代标准库 logging 的手写 dict 配置：

- request_id_var：基于 contextvars 的请求级上下文变量，贯穿视图与日志，实现全链路追踪；
- InterceptHandler：拦截标准库 logging（含 Django 内部 logger）的记录并转发到 Loguru，
  使第三方库与业务代码共用同一套格式化、分级与落盘策略；
- setup_loguru：配置 Loguru 的 sink（控制台 + 可选文件轮转）与 patcher（注入 request_id）；
- build_logging_config：生成 Django settings.LOGGING 所需的 dict，将根 / 各 logger 指向 InterceptHandler。

业务代码统一使用 Loguru 的 {}-style 占位（惰性格式化，避免无谓的字符串拼接）：

    from loguru import logger
    logger.info("用户 {} 登录成功", user_id)
"""

import logging
import sys
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

# 请求级上下文变量：默认 "-"，由 utils.middleware.RequestMetaMiddleware 在请求开始时写入。
# 定义于本模块（而非 middleware）以便日志 patcher 与中间件共享同一变量，且避免循环导入。
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# 控制台格式：时间 | 级别 | 模块:函数:行号 | request-id | 消息（含颜色标记）
_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "rid=<yellow>{extra[request_id]}</yellow> | "
    "<level>{message}</level>"
)
# 文件格式：与控制台一致但不含颜色标记，便于纯文本检索
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{function}:{line} | rid={extra[request_id]} | {message}"
)


class InterceptHandler(logging.Handler):
    """将标准库 logging 的记录转发到 Loguru。

    Django 及绝大多数第三方库都使用标准库 logging。把它们的 handler 换成 InterceptHandler 后，
    所有日志都会汇入 Loguru，由 Loguru 统一分级、格式化与落盘，避免出现两套并行的日志系统。
    """

    def emit(self, record: logging.LogRecord) -> None:
        # 将标准库级别名映射为 Loguru 级别；自定义级别回退到数字级别
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 复用标准库记录中已捕获的真实调用位置与 logger 名（record.name / funcName / lineno / pathname），
        # 通过 patch 覆盖 Loguru 的帧解析结果——否则 {name}:{function}:{line} 会落在 logging 内部帧，失去定位价值。
        # 同时在此显式写入 request_id，保证被拦截的第三方 / Django 日志也带上全链路追踪标识。
        request_id = request_id_var.get()
        logger.opt(exception=record.exc_info).patch(
            lambda loguru_record: loguru_record.update(
                name=record.name,
                module=record.module,
                function=record.funcName or "<module>",
                line=record.lineno,
                file={"name": Path(record.pathname).name, "path": record.pathname},
                extra={**loguru_record["extra"], "request_id": request_id},
            )
        ).log(level, record.getMessage())


def _inject_request_id(record) -> None:
    """Loguru patcher：为每条记录注入当前请求的 request_id（无请求上下文时为默认值）。"""
    record["extra"]["request_id"] = request_id_var.get()


def setup_loguru(
    level: str = "INFO",
    log_dir: str | Path | None = None,
    *,
    diagnose: bool = False,
) -> None:
    """初始化 Loguru：移除默认 sink，按配置重建控制台 / 文件 sink，并注册 request_id patcher。

    由 utils.apps.UtilsConfig.ready() 在应用装配阶段调用；多次调用保持幂等。

    参数：
        level：日志级别（控制台与文件共用），如 "DEBUG" / "INFO"。
        log_dir：文件日志目录；为空 / None 时仅输出到控制台
            （容器环境推荐留空，由 Docker / 日志采集系统统一收集 stderr）。
        diagnose：是否在异常回溯中展示变量值。开发可开启，生产务必关闭以免泄露敏感信息。
    """
    # 先注册默认 extra 与 patcher，确保任何记录都带有 request_id 键，格式化不会 KeyError
    logger.configure(extra={"request_id": "-"}, patcher=_inject_request_id)

    # 移除默认（及此前可能重复添加的）sink，保证多次调用幂等（如 runserver 自动重载）
    logger.remove()

    logger.add(
        sys.stderr,
        level=level,
        format=_CONSOLE_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=diagnose,
    )

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path / "app_{time:YYYY-MM-DD}.log",
            level=level,
            format=_FILE_FORMAT,
            rotation="00:00",  # 每日零点切分
            retention="14 days",  # 保留最近 14 天
            compression="zip",  # 历史日志压缩归档
            encoding="utf-8",
            enqueue=True,  # 多进程 / 多线程安全的异步写入
            backtrace=True,
            diagnose=False,  # 文件日志永不展示变量值
        )


def build_logging_config(level: str = "INFO") -> dict:
    """生成 Django settings.LOGGING：把标准库日志统一导向 InterceptHandler（→ Loguru）。

    这里仅负责“标准库 logging 的路由与级别闸门”；真正的格式化、落盘由 setup_loguru 决定。
    级别在两处生效：标准库 logger 级别（此处）与 Loguru sink 级别（setup_loguru），二者均取自 LOG_LEVEL。
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "loguru": {
                "class": "utils.log.InterceptHandler",
                "level": 0,  # 全部放行，最终级别由 sink 决定
            },
        },
        "root": {"handlers": ["loguru"], "level": level},
        "loggers": {
            # Django 各内部 logger 统一汇入 Loguru
            "django": {"handlers": ["loguru"], "level": level, "propagate": False},
            # 固定较高阈值，避免 dev 下 DEBUG 造成 SQL 日志洪水；排查 SQL 时临时调低即可
            "django.db.backends": {"handlers": ["loguru"], "level": "INFO", "propagate": False},
            # runserver 的请求行已由 RequestMetaMiddleware 记录（含 request-id 与耗时），此处降噪
            "django.server": {"handlers": ["loguru"], "level": "WARNING", "propagate": False},
            # 项目自身代码：允许 DEBUG，便于开发排障
            "utils": {"handlers": ["loguru"], "level": "DEBUG", "propagate": False},
        },
    }
