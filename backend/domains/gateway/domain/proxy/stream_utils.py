"""流式响应工具函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)


async def safe_aclose_stream(stream: Any) -> None:
    """安全关闭异步流/迭代器，忽略缺失 aclose 或关闭异常。

    用于客户端断开连接或异常退出时，主动释放上游 HTTP 连接与相关资源。
    """
    if stream is None:
        return
    aclose = getattr(stream, "aclose", None)
    if not callable(aclose):
        return
    try:
        await cast("Callable[[], Awaitable[Any]]", aclose)()
    except Exception as exc:
        logger.debug("safe_aclose_stream: error closing stream: %s", exc)


__all__ = ["safe_aclose_stream"]
