"""
Logging Utilities - 日志工具

架构说明：
- get_logger() 是无依赖的，可以被任何模块安全导入
- setup_logging() 需要 settings，在应用启动时调用
"""

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    """获取日志器（无依赖，可安全导入）"""
    return logging.getLogger(name)


def setup_logging(
    log_level: str | None = None,
    log_format: str = "text",
    is_development: bool | None = None,
) -> None:
    """设置日志

    Args:
        log_level: 日志级别，默认从环境变量 LOG_LEVEL 读取
        log_format: 日志格式 (text/json)
        is_development: 是否开发环境，默认从 APP_ENV 判断
    """
    # 从环境变量获取配置（避免循环依赖）
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    if is_development is None:
        is_development = os.getenv("APP_ENV", "development") == "development"

    # 开发环境下使用 DEBUG 级别
    level = logging.DEBUG if is_development else getattr(logging, log_level.upper(), logging.INFO)

    # 配置应用日志器（不干扰 uvicorn 的日志）
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)

    # 如果没有处理器，添加一个
    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        app_logger.addHandler(handler)
        app_logger.propagate = False  # 不传播到根日志器，避免重复

    # 设置第三方库日志级别
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class LoggerMixin:
    """日志混入类"""

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__name__)
