"""
Sentry 集成 - 错误监控和性能追踪

提供 Sentry 错误监控功能，捕获未处理的异常并上报。
"""

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from utils.logging import get_logger

logger = get_logger(__name__)

# Sentry 初始化状态
_sentry_initialized = False


def _before_send_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """在事件发送前修改事件数据

    Args:
        event: Sentry 事件数据
        _hint: 提示信息

    Returns:
        修改后的事件数据，返回 None 则取消发送
    """
    # 添加自定义标签
    request_data = event.get("request", {})
    if request_data:
        # 移除敏感的请求头
        headers = request_data.get("headers", {})
        sensitive_headers = ["authorization", "cookie", "x-api-key", "x-auth-token"]
        for key in list(headers.keys()):
            if key.lower() in sensitive_headers:
                headers[key] = "[REDACTED]"

    # 移除敏感的查询参数
    query_string = request_data.get("query_string", "")
    if query_string:
        # 简单处理：可以进一步细化
        pass

    return event


def _before_send_transaction(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """在事务发送前修改数据

    Args:
        event: Sentry 事务数据
        _hint: 提示信息

    Returns:
        修改后的事务数据
    """
    return event


def init_sentry(
    dsn: str,
    environment: str = "production",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.0,
    enabled: bool = True,
) -> bool:
    """初始化 Sentry

    Args:
        dsn: Sentry DSN
        environment: 环境名称 (development | staging | production)
        traces_sample_rate: 性能监控采样率 (0.0 - 1.0)
        profiles_sample_rate: 性能分析采样率 (0.0 - 1.0)
        enabled: 是否启用 Sentry

    Returns:
        是否成功初始化
    """
    global _sentry_initialized

    if not enabled:
        logger.info("Sentry is disabled")
        return False

    if not dsn:
        logger.warning("Sentry DSN is empty, skipping initialization")
        return False

    if _sentry_initialized:
        logger.warning("Sentry is already initialized")
        return True

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            before_send=_before_send_event,
            before_send_transaction=_before_send_transaction,
            integrations=[
                FastApiIntegration(),
                RedisIntegration(),
                SqlalchemyIntegration(),
                HttpxIntegration(),
            ],
            # 过滤敏感信息
            send_default_pii=False,  # 不发送个人身份信息
            # 服务器名称
            server_name=None,  # 使用 Sentry 默认
            # 发布版本
            release=None,  # 可以从环境变量读取
            # 采样配置
            sample_rate=1.0,  # 错误采样率
        )
        _sentry_initialized = True
        logger.info(
            "Sentry initialized: environment=%s, traces_sample_rate=%s",
            environment,
            traces_sample_rate,
        )
        return True
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", e, exc_info=True)
        return False


def is_sentry_initialized() -> bool:
    """检查 Sentry 是否已初始化"""
    return _sentry_initialized


def capture_exception(exception: Exception, level: str | None = None, **tags: str) -> str | None:
    """捕获异常并发送到 Sentry

    Args:
        exception: 异常对象
        level: 日志级别 (fatal | error | warning | info | debug)
        **tags: 自定义标签

    Returns:
        Sentry 事件 ID，如果未初始化则返回 None
    """
    if not _sentry_initialized:
        return None

    with sentry_sdk.push_scope() as scope:
        # 添加自定义标签
        for key, value in tags.items():
            scope.set_tag(key, value)

        # 设置级别
        if level:
            scope.set_level(level)

        # 发送异常
        event_id = sentry_sdk.capture_exception(exception)
        logger.debug("Exception captured by Sentry: %s", event_id)
        return event_id


def capture_message(
    message: str,
    level: str = "info",
    **tags: str,
) -> str | None:
    """捕获消息并发送到 Sentry

    Args:
        message: 消息内容
        level: 日志级别 (fatal | error | warning | info | debug)
        **tags: 自定义标签

    Returns:
        Sentry 事件 ID，如果未初始化则返回 None
    """
    if not _sentry_initialized:
        return None

    with sentry_sdk.push_scope() as scope:
        # 添加自定义标签
        for key, value in tags.items():
            scope.set_tag(key, value)

        # 发送消息
        event_id = sentry_sdk.capture_message(message, level=level)
        logger.debug("Message captured by Sentry: %s", event_id)
        return event_id


def set_user_context(user_id: str, email: str | None = None, **kwargs: str) -> None:
    """设置用户上下文

    Args:
        user_id: 用户 ID
        email: 用户邮箱
        **kwargs: 其他用户信息
    """
    if not _sentry_initialized:
        return

    user_data = {"id": user_id, **kwargs}
    if email:
        user_data["email"] = email

    sentry_sdk.set_user(user_data)


def clear_user_context() -> None:
    """清除用户上下文"""
    if not _sentry_initialized:
        return
    sentry_sdk.set_user(None)


def set_tag(key: str, value: str) -> None:
    """设置标签

    Args:
        key: 标签键
        value: 标签值
    """
    if not _sentry_initialized:
        return
    sentry_sdk.set_tag(key, value)


def set_context(key: str, value: dict[str, Any]) -> None:
    """设置上下文

    Args:
        key: 上下文键
        value: 上下文值
    """
    if not _sentry_initialized:
        return
    sentry_sdk.set_context(key, value)


def add_breadcrumb(
    message: str,
    category: str = "custom",
    level: str = "info",
    **data: Any,
) -> None:
    """添加面包屑

    Args:
        message: 消息
        category: 分类
        level: 级别
        **data: 附加数据
    """
    if not _sentry_initialized:
        return
    sentry_sdk.add_breadcrumb(
        {
            "message": message,
            "category": category,
            "level": level,
            "data": data,
        }
    )
