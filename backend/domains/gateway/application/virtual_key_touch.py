"""虚拟 Key 使用回写：fire-and-forget，避免阻塞鉴权热路径。"""

from __future__ import annotations

import asyncio
import uuid

from domains.gateway.application.proxy_deferred_tasks import register_proxy_deferred_task
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from libs.db.database import get_session_context, prefer_background_pool
from utils.logging import get_logger

logger = get_logger(__name__)


async def _touch_virtual_key_used(vkey_id: uuid.UUID) -> None:
    try:
        with prefer_background_pool():
            async with get_session_context() as session:
                await VirtualKeyRepository(session).touch_used(vkey_id)
    except Exception:
        logger.exception("Async vkey touch_used failed for %s", vkey_id)


def schedule_virtual_key_touch(vkey_id: uuid.UUID) -> None:
    """登记后台任务更新 ``last_used_at`` / ``usage_count``（不阻塞请求）。"""
    task = asyncio.create_task(_touch_virtual_key_used(vkey_id))
    register_proxy_deferred_task(task)


__all__ = ["schedule_virtual_key_touch"]
