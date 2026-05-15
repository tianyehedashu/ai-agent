"""视频生成：模型目录与厂商 API 入参映射。

- **内置**：与 GIIKIN ``VideoAPIClient.submit`` 已对接的模型 ID（如 ``openai::sora2.0``）。
- **网关扩展**：``GatewayModel`` 上 ``supports_video_gen`` + ``video_vendor_model_id``（或兼容
  ``giikin_video_model``）时，合并进列表；``video_durations`` 为整数数组（可选）。

执行仍走 ``VideoAPIClient``（厂商 HTTP），不经过 LiteLLM；「模型」在此指 **产品侧可选能力 +
  厂商 payload 中的 model 字段**，与对话网关模型正交。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 与 VideoAPIClient / video_gen_tasks 落库字段对齐的模型 ID（无网关配置时的默认目录）。
_BUILTIN: tuple[dict[str, Any], ...] = (
    {
        "value": "openai::sora1.0",
        "label": "Sora 1.0",
        "durations": [5, 10, 15, 20],
        "max_reference_images": 8,
        "supports_image_to_video": True,
        "source": "builtin",
    },
    {
        "value": "openai::sora2.0",
        "label": "Sora 2.0",
        "durations": [5, 10, 15],
        "max_reference_images": 8,
        "supports_image_to_video": True,
        "source": "builtin",
    },
)

VALID_VIDEO_MODEL_IDS: Final[frozenset[str]] = frozenset(str(x["value"]) for x in _BUILTIN)


def default_video_model_id() -> str:
    return str(_BUILTIN[-1]["value"])


def list_builtin_video_models() -> list[dict[str, Any]]:
    """仅内置厂商模型（测试或与 ``list_merged_video_models`` 对比时使用）。"""
    return [dict(x) for x in _BUILTIN]


def _fallback_duration_set(vendor_model_id: str) -> set[int]:
    """无 ``video_durations`` tag 时的保守默认（与历史 Sora 规则一致）。"""
    if "sora1" in vendor_model_id:
        return {5, 10, 15, 20}
    return {5, 10, 15}


def allowed_durations_for_video_model(catalog: list[dict[str, Any]], vendor_model_id: str) -> set[int]:
    """从合并目录解析某 ``value``（厂商 model 字符串）允许的时长集合。"""
    for entry in catalog:
        if str(entry.get("value")) == vendor_model_id:
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
    return _fallback_duration_set(vendor_model_id)


async def list_merged_video_models(session: AsyncSession) -> list[dict[str, Any]]:
    """内置模型 + 网关可见 ``model_type=video`` 行（须带 ``video_vendor_model_id``）。"""
    from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
    from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter

    merged: list[dict[str, Any]] = [dict(x) for x in _BUILTIN]
    seen: set[str] = {str(x["value"]) for x in merged}

    try:
        catalog = get_model_catalog_adapter(session)
        team_id = resolve_internal_gateway_team_id()
        rows = await catalog.list_visible_models(billing_team_id=team_id, model_type="video")
    except Exception:
        logger.warning("list_merged_video_models: gateway catalog skipped", exc_info=True)
        return merged

    for item in rows:
        vendor_model = item.get("video_vendor_model_id")
        if not isinstance(vendor_model, str) or not vendor_model.strip():
            logger.debug(
                "list_merged_video_models: skip gateway row %s (missing video_vendor_model_id)",
                item.get("id"),
            )
            continue
        vendor_model = vendor_model.strip()
        if vendor_model in seen:
            continue
        raw_caps = item.get("capabilities")
        caps: dict[str, Any] = raw_caps if isinstance(raw_caps, dict) else {}
        max_ref = int(caps.get("max_reference_images", 8) or 8)
        durs = item.get("video_durations")
        durations: list[int]
        if isinstance(durs, list) and durs:
            durations = []
            for d in durs:
                if isinstance(d, int):
                    durations.append(d)
                elif isinstance(d, float) and d.is_integer():
                    durations.append(int(d))
            if not durations:
                durations = sorted(_fallback_duration_set(vendor_model))
        else:
            durations = sorted(_fallback_duration_set(vendor_model))

        merged.append(
            {
                "value": vendor_model,
                "label": str(item.get("display_name") or vendor_model),
                "durations": durations,
                "max_reference_images": max_ref,
                "supports_image_to_video": bool(caps.get("supports_image_to_video", True)),
                "source": "gateway",
            }
        )
        seen.add(vendor_model)

    return merged


async def allowed_video_model_ids(session: AsyncSession) -> frozenset[str]:
    """创建/更新任务时允许的 ``model``（厂商 config.model）取值集合。"""
    items = await list_merged_video_models(session)
    return frozenset(str(x["value"]) for x in items)


__all__ = [
    "VALID_VIDEO_MODEL_IDS",
    "allowed_durations_for_video_model",
    "allowed_video_model_ids",
    "default_video_model_id",
    "list_builtin_video_models",
    "list_merged_video_models",
]
