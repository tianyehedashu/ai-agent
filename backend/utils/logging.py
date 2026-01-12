"""
Logging Utilities - 日志工具
"""

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """设置日志"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 配置根日志
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(log_level)
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
