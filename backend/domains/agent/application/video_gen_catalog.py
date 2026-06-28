"""视频生成：模型目录（基于 Gateway ``model_type=video``）。

执行经 Gateway 代理（LiteLLM ``avideo_generation`` / 火山直连），``value`` 即网关
``system_gateway_models.name``（LiteLLM ``model`` 参数）。能力字段（时长、参考图上限）
来自 ``GatewayModel.tags``（经 ``list_visible_models`` 注入的 ``video_durations`` /
``capabilities``）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
import uuid

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 无 ``video_durations`` tag 时的默认时长集合（秒）。
_DEFAULT_DURATIONS: tuple[int, ...] = (5, 10, 15)


def _parse_durations(raw: Any) -> list[int]:
    if not isinstance(raw, list) or not raw:
        return list(_DEFAULT_DURATIONS)
    out: list[int] = []
    for d in raw:
        if isinstance(d, int):
            out.append(d)
        elif isinstance(d, float) and d.is_integer():
            out.append(int(d))
    return out or list(_DEFAULT_DURATIONS)


def allowed_durations_for_video_model(
    catalog: list[dict[str, Any]], model_id: str
) -> set[int]:
    """从合并目录解析某 ``value``（网关 model_id）允许的时长集合。"""
    for entry in catalog:
        if str(entry.get("value")) == model_id:
            durs = entry.get("durations")
            if isinstance(durs, list) and durs:
                out: set[int] = set()
                for d in durs:
                    if isinstance(d, int):
                        out.add(d)
                    elif isinstance(d, float) and d.is_integer():
                        out.add(int(d))
                if out:
                    return out
            break
    return set(_DEFAULT_DURATIONS)


async def list_merged_video_models(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """网关可见 ``model_type=video`` 行（``value`` 即网关 model_id）。

    与 ``GET /gateway/models/available?type=video`` 对齐：合并系统可见模型与个人团队模型。
    """
    from domains.gateway.application.bridge.internal_bridge_actor import resolve_internal_gateway_team_id
    from domains.gateway.application.catalog.model_selector_reads import (
        list_available_system_models,
        list_personal_models_for_selector,
    )
    from domains.gateway.application.catalog.sql_model_catalog import get_model_catalog_adapter

    try:
        catalog = get_model_catalog_adapter(session)
        team_id = resolve_internal_gateway_team_id()
        rows = await list_available_system_models(
            catalog,
            model_type="video",
            billing_team_id=team_id,
            user_id=user_id,
        )
        if user_id is not None:
            personal = await list_personal_models_for_selector(
                catalog,
                user_id,
                model_type="video",
            )
            rows = [*rows, *personal]
    except Exception:
        logger.warning("list_merged_video_models: gateway catalog skipped", exc_info=True)
        return []

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        model_id = model_id.strip()
        if model_id in seen:
            continue
        raw_caps = item.get("capabilities")
        caps: dict[str, Any] = raw_caps if isinstance(raw_caps, dict) else {}
        max_ref = int(caps.get("max_reference_images", 8) or 8)
        durs = _parse_durations(item.get("video_durations"))
        merged.append(
            {
                "value": model_id,
                "label": str(item.get("display_name") or model_id),
                "durations": durs,
                "max_reference_images": max_ref,
                "supports_image_to_video": bool(caps.get("supports_image_to_video", True)),
                "source": "gateway",
            }
        )
        seen.add(model_id)
    return merged


async def allowed_video_model_ids(session: AsyncSession) -> frozenset[str]:
    """创建/更新任务时允许的 ``model``（网关 model_id）取值集合。"""
    items = await list_merged_video_models(session)
    return frozenset(str(x["value"]) for x in items)


__all__ = [
    "allowed_durations_for_video_model",
    "allowed_video_model_ids",
    "list_merged_video_models",
]
