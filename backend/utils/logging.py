"""
Logging Utilities - 日志工具
"""

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """设置日志"""
    # 开发环境下使用 DEBUG 级别以便看到所有错误
    if settings.is_development:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 配置应用日志器（不干扰 uvicorn 的日志）
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)

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


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


class LoggerMixin:
    """日志混入类"""

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__name__)
