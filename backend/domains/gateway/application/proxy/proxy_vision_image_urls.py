"""Chat 代理出站前：将本地上传图片 URL 内联为 data URL，供火山等上游使用。"""

from __future__ import annotations

import base64
from typing import Any

from domains.gateway.application.bridge.listing_studio_image_port_registry import (
    get_listing_studio_local_image_port,
)
from domains.gateway.application.ports import ListingStudioLocalImagePort
from domains.gateway.domain.proxy.vision_image_mime import guess_vision_inline_mime
from domains.gateway.domain.proxy.vision_image_url import (
    parse_listing_studio_image_filename,
    should_inline_vision_image_url,
)
from libs.db.database import get_session_context
from utils.logging import get_logger

logger = get_logger(__name__)


def _bytes_to_data_url(content: bytes, mime: str) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _resolve_to_data_url(
    raw_url: str,
    image_port: ListingStudioLocalImagePort,
) -> str | None:
    if not should_inline_vision_image_url(raw_url):
        return None
    filename = parse_listing_studio_image_filename(raw_url)
    if filename is None:
        return None
    path = await image_port.resolve_local_image_path(filename)
    if path is None:
        logger.warning(
            "vision image inline skipped (local file missing): filename=%s url=%s",
            filename,
            raw_url[:200],
        )
        return None
    return _bytes_to_data_url(path.read_bytes(), guess_vision_inline_mime(path))


async def _transform_message_content_async(
    content: list[Any],
    image_port: ListingStudioLocalImagePort,
) -> tuple[list[Any], bool]:
    new_parts: list[Any] = []
    changed = False
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            new_parts.append(part)
            continue
        image_url = part.get("image_url")
        if not isinstance(image_url, dict):
            new_parts.append(part)
            continue
        raw = image_url.get("url")
        if not isinstance(raw, str):
            new_parts.append(part)
            continue
        data_url = await _resolve_to_data_url(raw, image_port)
        if data_url is None:
            new_parts.append(part)
            continue
        new_parts.append({"type": "image_url", "image_url": {"url": data_url}})
        changed = True
    return new_parts, changed


async def inline_vision_image_urls_in_messages(
    messages: list[Any],
    image_port: ListingStudioLocalImagePort,
) -> list[Any]:
    """将 messages 中需内联的 image_url 转为 data URL（原地结构拷贝）。"""
    out: list[Any] = []
    any_changed = False
    for msg in messages:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue
        new_content, changed = await _transform_message_content_async(content, image_port)
        if changed:
            out.append({**msg, "content": new_content})
            any_changed = True
        else:
            out.append(msg)
    return out if any_changed else messages


def _messages_have_image_url_parts(messages: list[Any]) -> bool:
    """预扫：仅当存在至少一条 ``content`` block 为 ``type=="image_url"`` 时返回 True。

    用于让 :func:`inline_vision_image_urls_in_kwargs` 在无图请求上避免创建独立的
    ``AsyncSession`` 与 ``StorageConfigService`` 查询 —— 表论/外部行为与原路径完全等价
    （原路径在这种场景也仅返回同一 ``messages`` 对象），仅仅提前结束。
    """
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


async def inline_vision_image_urls_in_kwargs(
    kwargs: dict[str, Any],
    *,
    image_port: ListingStudioLocalImagePort | None = None,
) -> dict[str, Any]:
    """在 LiteLLM 调用前处理 kwargs.messages 中的参考图 URL。

    默认端口经 **独立** ``AsyncSession`` 构建：``StorageConfigService.build_image_store``
    会在读配置后 ``rollback`` 以释放连接；若复用 FastAPI 请求级 session，会破坏同请求
    后续 ORM 访问（``greenlet_spawn`` / ``await_only``）。

    性能：当 ``image_port`` 未注入且 messages 中没有任何 ``type=="image_url"`` block 时，
    直接返回原 kwargs，**不创建 session / 不查 DB**。与打开 session 后发现无图再空走一
    轮的之前版本表论等价。
    """
    messages = kwargs.get("messages")
    if not isinstance(messages, list):
        return kwargs
    if image_port is not None:
        new_messages = await inline_vision_image_urls_in_messages(messages, image_port)
    else:
        if not _messages_have_image_url_parts(messages):
            return kwargs
        async with get_session_context() as isolated:
            port = get_listing_studio_local_image_port(isolated)
            new_messages = await inline_vision_image_urls_in_messages(messages, port)
    if new_messages is messages:
        return kwargs
    return {**kwargs, "messages": new_messages}


__all__ = [
    "_messages_have_image_url_parts",
    "inline_vision_image_urls_in_kwargs",
    "inline_vision_image_urls_in_messages",
]
