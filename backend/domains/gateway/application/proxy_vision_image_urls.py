"""Chat 代理出站前：将本地上传图片 URL 内联为 data URL，供火山等上游使用。"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from domains.gateway.application.listing_studio_image_port_registry import (
    get_listing_studio_local_image_port,
)
from domains.gateway.application.ports import ListingStudioLocalImagePort
from domains.gateway.domain.policies.vision_image_mime import guess_vision_inline_mime
from domains.gateway.domain.policies.vision_image_url import (
    parse_listing_studio_image_filename,
    should_inline_vision_image_url,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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


async def inline_vision_image_urls_in_kwargs(
    session: AsyncSession,
    kwargs: dict[str, Any],
    *,
    image_port: ListingStudioLocalImagePort | None = None,
) -> dict[str, Any]:
    """在 LiteLLM 调用前处理 kwargs.messages 中的参考图 URL。"""
    messages = kwargs.get("messages")
    if not isinstance(messages, list):
        return kwargs
    port = image_port or get_listing_studio_local_image_port(session)
    new_messages = await inline_vision_image_urls_in_messages(messages, port)
    if new_messages is messages:
        return kwargs
    return {**kwargs, "messages": new_messages}


__all__ = [
    "inline_vision_image_urls_in_kwargs",
    "inline_vision_image_urls_in_messages",
]
