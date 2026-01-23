"""
结构化日志

提供结构化日志记录功能
"""

import json
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


class StructuredLogger:
    """
    结构化日志记录器

    提供结构化日志记录，便于日志分析和监控
    """

    def __init__(self, name: str | None = None) -> None:
        self.logger = get_logger(name or __name__)

    def log(
        self,
        level: str,
        message: str,
        **kwargs: Any,
    ) -> None:
        """
        记录结构化日志

        Args:
            level: 日志级别 (debug, info, warning, error)
            message: 日志消息
            **kwargs: 额外字段
        """
        log_data = {
            "message": message,
            **kwargs,
        }

        log_message = json.dumps(log_data, ensure_ascii=False)

        if level == "debug":
            self.logger.debug(log_message)
        elif level == "info":
            self.logger.info(log_message)
        elif level == "warning":
            self.logger.warning(log_message)
        elif level == "error":
            self.logger.error(log_message)
        else:
            self.logger.info(log_message)

    def debug(self, message: str, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志"""
        self.log("debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """记录 INFO 级别日志"""
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """记录 WARNING 级别日志"""
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """记录 ERROR 级别日志"""
        self.log("error", message, **kwargs)

    def log_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        level: str = "info",
    ) -> None:
        """
        记录事件日志

        Args:
            event_type: 事件类型
            event_data: 事件数据
            level: 日志级别
        """
        self.log(
            level,
            f"Event: {event_type}",
            event_type=event_type,
            **event_data,
        )
